# Báo Cáo Lab Day 21 - CI/CD cho AI Systems

| | |
|---|---|
| Họ và tên | Trần Mạnh Tùng |
| MSSV | 2A202602879 |
| Lớp / Khóa | K4 |
| Repo GitHub | https://github.com/manhtungai247/K4-L3L4-Track2-Day21-TranManhTung-2A202602879-CI-CD-for-AI-Systems |
| Ngày nộp | 07/10/2026 |

---

## 1. Bộ Siêu Tham Số Đã Chọn và Lý Do

| Lần chạy | n_estimators | learning_rate | max_depth | f1_score | accuracy |
|---|---:|---:|---:|---:|---:|
| 1 | 100 | 0.1 | 3 | 0.7109 | 0.8780 |
| 2 | 50 | 0.05 | 2 | 0.6051 | 0.8460 |
| 3 | 200 | 0.1 | 5 | 0.7149 | 0.8740 |

**Bộ siêu tham số chọn:** `n_estimators=200`, `learning_rate=0.1`, `max_depth=5`. Lần 3 có F1 cao nhất (0,7149), dù accuracy cao nhất thuộc lần 1 (0,8780). Điều này cho thấy accuracy tổng thể chưa phản ánh đầy đủ khả năng nhận diện lớp thu nhập cao. Mô hình nông, ít cây ở lần 2 đạt F1 thấp hơn. Ba cấu hình thay đổi nhiều tham số cùng lúc nên chỉ kết luận tổ hợp lần 3 tốt nhất trong các lần đã thử; chưa tách riêng ảnh hưởng từng tham số.

## 2. Vì Sao Ngưỡng Chất Lượng Đặt Trên F1 Chứ Không Phải Accuracy

Lớp dương `target=1` chiếm khoảng 24,8% dữ liệu. Một mô hình luôn đoán `target=0` vẫn có thể đạt xấp xỉ 75,2% accuracy, nhưng không nhận diện được trường hợp thu nhập cao nào và F1 của lớp dương bằng 0. Vì vậy accuracy có thể trông khá cao trong khi mô hình bỏ sót toàn bộ nhóm cần dự đoán. Quality Gate dùng F1 mặc định nhị phân từ `f1_score(y_eval, preds)`, phản ánh precision và recall của lớp dương. Không dùng `average="macro"` hoặc `average="weighted"` vì các cách lấy trung bình đó gộp điểm nhiều lớp, không trực tiếp kiểm tra hiệu quả của lớp dương theo yêu cầu lab.

## 3. Khó Khăn Gặp Phải và Cách Giải Quyết

| Khó khăn | Nguyên nhân | Cách giải quyết |
|---|---|---|
| Cài thư viện thất bại với NumPy prerelease | Môi trường Python ban đầu không có bản wheel tương thích | Chuyển sang Python 3.11 và dùng các phiên bản phụ thuộc đã ghim trong `requirements.txt`. |
| DVC truy cập S3 báo AccessDenied | URL remote và quyền bucket/prefix chưa khớp | Cấu hình remote tới `s3://<bucket>/dvc`; `dvc status -c` hiện xác nhận cache và remote đồng bộ. |
| SSH tới EC2 bị timeout | IP public của mạng hiện tại khác IP trong allowlist cổng 22 | Cập nhật nguồn SSH thành IP hiện tại `/32`; cần chạy lại `Test-NetConnection` và SSH để xác nhận sau khi lưu luật. |

## 4. So Sánh Bước 2 và Bước 3

| Chạy tái lập cục bộ và CI với cùng tham số/holdout | f1_score | accuracy |
|---|---:|---:|
| Bước 2 (`train_batch1`, 22.361 mẫu) | 0.7149 | 0.8740 |
| Bước 3 (`train_batch1` + `train_batch2`, 44.722 mẫu) | 0.7354 | 0.8820 |

**Nhận xét:** Log CI xác nhận metric trùng với lần tái lập cục bộ. Khi thêm dữ liệu cùng nguồn, F1 tăng 0,0205 và accuracy tăng 0,0080; đây là kết quả quan sát được, không chứng minh mọi dữ liệu bổ sung đều cải thiện mô hình. Hai pipeline CI cho Bước 2 và Bước 3 đều hoàn thành Unit Test, Train, Quality Gate và Release. Mỗi lần chạy lưu `report.json` thành artifact `report` trên GitHub Actions.

## 5. Triển Khai và Kiểm Tra CI/CD

| Giai đoạn | Commit / workflow run | Kết quả |
|---|---|---|
| Bước 2 — train với 22.361 mẫu | [`dd96caa` / run #3](https://github.com/manhtungai247/K4-L3L4-Track2-Day21-TranManhTung-2A202602879-CI-CD-for-AI-Systems/actions/runs/37628485660) | Unit Test, Train, Quality Gate, Release đều thành công |
| Bước 3 — train với 44.722 mẫu | [`2745810` / run #4](https://github.com/manhtungai247/K4-L3L4-Track2-Day21-TranManhTung-2A202602879-CI-CD-for-AI-Systems/actions/runs/37628998637) | Unit Test, Train, Quality Gate, Release đều thành công |

GitHub Actions lấy AWS credentials bằng OIDC với trust policy giới hạn vào repository và nhánh `main`; job Release promote model đạt Quality Gate lên S3 rồi yêu cầu Systems Manager restart dịch vụ trên EC2. Không lưu access key AWS dài hạn trong GitHub.

Sau lần deploy Bước 3, endpoint `GET /healthz` trả `{"status":"ok"}` và một yêu cầu `POST /score` với 10 đặc trưng mẫu trả `{"prediction":1,"label":"thu_nhap_cao"}`. Security Group chỉ mở SSH/22 và API/8080 từ IP client được allowlist dạng `/32`.
