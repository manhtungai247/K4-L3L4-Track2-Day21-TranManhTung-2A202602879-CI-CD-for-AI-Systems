# Bước 2 - Pipeline CI/CD với DVC, Amazon S3, EC2 và GitHub Actions

Mục tiêu: lưu dữ liệu và mô hình trên S3, chạy kiểm thử/huấn luyện tự động khi cập nhật mã hoặc con trỏ DVC, chỉ triển khai lên EC2 khi `f1_score >= 0.65`.

## 2.1. Chuẩn bị AWS và bucket S3

Cài AWS CLI và cấu hình thông tin xác thực trên máy cá nhân bằng `aws configure` hoặc AWS IAM Identity Center. Không lưu access key trong Git, file dự án hay nội dung gửi lên chat. Chọn region bạn sẽ dùng cho cả bucket và EC2, rồi kiểm tra phiên đăng nhập:

```powershell
aws sts get-caller-identity
$env:AWS_DEFAULT_REGION = "<region>"
$env:ARTIFACT_BUCKET = "<ten-bucket-duy-nhat>"
aws s3api create-bucket --bucket $env:ARTIFACT_BUCKET --region $env:AWS_DEFAULT_REGION
```

Với region ngoài `us-east-1`, lệnh tạo bucket cần thêm `--create-bucket-configuration LocationConstraint=$env:AWS_DEFAULT_REGION`. Nếu bucket đã tồn tại và thuộc tài khoản của bạn, bỏ qua bước tạo. Bật Block Public Access và mã hóa mặc định của bucket; không cấp quyền public.

Tạo IAM policy giới hạn đúng bucket/prefix. Người chạy DVC cần `s3:ListBucket` trên bucket (điều kiện prefix `dvc/*`) và `s3:GetObject`, `s3:PutObject`, `s3:DeleteObject` trên `arn:aws:s3:::<bucket>/dvc/*`. Workflow hiện dùng chung một cặp GitHub AWS keys cho cả Train và Release, nên IAM principal đó cần hợp quyền: đọc DVC ở `dvc/*`, ghi candidate ở `artifacts/candidates/*`, đọc candidate ở prefix đó để promote, và ghi `artifacts/current/model.joblib`. Nếu tách credentials giữa hai job, cấp mỗi principal đúng quyền riêng tương ứng. EC2 instance profile chỉ cần `s3:GetObject` trên object current model. Không dùng quyền quản trị toàn AWS.

## 2.2. Đưa dữ liệu vào DVC remote

Repo đã được `dvc init` và có các con trỏ `data/train_batch1.csv.dvc`, `data/holdout.csv.dvc`, `data/train_batch2.csv.dvc`. Trên máy cá nhân, thêm remote dùng tên bucket của bạn; `--local` ghi URL vào `.dvc/config.local` (đã bị Git bỏ qua):

```powershell
dvc remote add -d --local labstore "s3://$env:ARTIFACT_BUCKET/dvc"
dvc push
```

Đẩy object lên S3 trước khi commit/push con trỏ. Khi cập nhật dữ liệu, chạy `dvc add data/train_batch1.csv`, rồi lần lượt `dvc push`, `git add data/train_batch1.csv.dvc`, `git commit -m "data: update training data"`, `git push origin main`. Git chỉ chứa các tệp `.dvc`, không chứa CSV. GitHub Actions được kích hoạt khi có thay đổi `data/*.dvc`, `src/*.py`, `tests/*.py`, `params.yaml`, `requirements.txt` hoặc workflow.

## 2.3. Cấu hình GitHub OIDC, SSM và EC2

Không tạo access key dài hạn cho GitHub. Trong IAM, tạo GitHub OIDC identity provider với issuer `https://token.actions.githubusercontent.com`, audience `sts.amazonaws.com`, rồi tạo role có trust policy giới hạn đúng repository và nhánh `main`:

```json
{
  "Version": "2012-10-17",
  "Statement": [{
    "Effect": "Allow",
    "Principal": {"Federated": "arn:aws:iam::<account-id>:oidc-provider/token.actions.githubusercontent.com"},
    "Action": "sts:AssumeRoleWithWebIdentity",
    "Condition": {
      "StringEquals": {"token.actions.githubusercontent.com:aud": "sts.amazonaws.com"},
      "StringLike": {"token.actions.githubusercontent.com:sub": "repo:manhtungai247/K4-L3L4-Track2-Day21-TranManhTung-2A202602879-CI-CD-for-AI-Systems:ref:refs/heads/main"}
    }
  }]
}
```

Gắn role một policy giới hạn vào bucket đã chọn: cho Train quyền `s3:ListBucket` giới hạn prefix `dvc/*`, `s3:GetObject` trên `dvc/*`, ghi candidate trên `artifacts/candidates/*`; cho Release đọc candidate, ghi đúng `artifacts/current/model.joblib`, và gọi `ssm:SendCommand` lên đúng EC2 instance với document `AWS-RunShellScript`, cùng `ssm:GetCommandInvocation`. Tạo policy resource ARN theo region, account và bucket thực tế; không dùng `*` cho bucket/object hay instance.

Trong GitHub → Settings → Secrets and variables → Actions → Variables, tạo `AWS_ROLE_TO_ASSUME` (ARN của role), `AWS_DEFAULT_REGION`, `ARTIFACT_BUCKET`, và `EC2_INSTANCE_ID`. Workflow yêu cầu `id-token: write`; Train và Release nhận credential ngắn hạn bằng `aws-actions/configure-aws-credentials`.

Gắn cho instance role policy `AmazonSSMManagedInstanceCore` và quyền chỉ đọc `s3://<bucket>/artifacts/current/model.joblib`. Đảm bảo SSM Agent đang chạy và instance đăng ký Online trong Systems Manager → Fleet Manager. Cài Python, clone repo, cài dependencies, tạo systemd service `income-api` chạy `uvicorn src.serve:app --host 0.0.0.0 --port 8080`; đặt `ARTIFACT_BUCKET` và `AWS_DEFAULT_REGION` trong cấu hình service. API lấy model từ S3 lúc khởi động; không đặt AWS access key trên EC2. Security group chỉ mở SSH (TCP 22) tới IP quản trị `/32` khi cần SSH tương tác; CI deploy gọi SSM, nên không cần mở SSH cho GitHub runners. Chỉ mở TCP 8080 tới dải client cần gọi API.

## 2.4. Luồng CI/CD và kiểm tra

Workflow gồm bốn job: Unit Test chạy pytest trên Python 3.11; Train tải train/holdout bằng DVC, huấn luyện, lưu `outputs/report.json`, đẩy model candidate theo commit SHA lên S3 và xuất F1; Quality Gate dừng pipeline nếu F1 dưới 0.65; Release chỉ chạy sau gate, promote candidate đã đạt chuẩn thành `artifacts/current/model.joblib`, gọi SSM restart `income-api` và kiểm tra `/healthz` trên EC2.

Sau khi cấu hình bucket, credentials, EC2 và secrets, kiểm tra trên GitHub Actions cả bốn job đều xanh. Gọi API từ máy cá nhân:

```powershell
Invoke-RestMethod -Method Get "http://$env:VM_IP:8080/healthz"
$body = @{ features = @(28,2,14,2,11,0,1,0,0,45) } | ConvertTo-Json
Invoke-RestMethod -Method Post "http://$env:VM_IP:8080/score" -ContentType "application/json" -Body $body
```

Chỉ xác nhận triển khai hoàn tất sau khi pipeline chạy thành công và `/healthz`, `/score` phản hồi từ EC2.
