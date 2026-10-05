# VISTA — Django application

Ứng dụng điểm danh dùng Django, OpenCV và InsightFace. Xem [README chính](../README.md) để biết đầy đủ chức năng, kiến trúc, cài đặt, API, dữ liệu và giới hạn.

## Chạy nhanh trên Windows

Thực hiện tại `django_app`, với Python 3.12 x64 và cấu hình GPU đã mô tả trong README chính:

```powershell
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_windows.ps1
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Nếu đã có venv và database, chỉ cần lệnh chạy server. Mở **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**; dừng bằng **Ctrl+C**. Không dùng `https://127.0.0.1/`.

Không cài `onnxruntime` CPU cùng `onnxruntime-gpu` trong một venv. Dependency chốt cho Windows/Python 3.12/GPU NVIDIA; script dùng `--no-deps` để giữ đúng runtime.

## Kiểm thử

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test portal
node --test tests/camera-policy.test.cjs tests/face-overlay.test.cjs
```

Django gồm 46 test (mặc định bỏ qua 1 test GPU thực); Node gồm 21 test. Test GPU cần `RUN_VISION_TESTS=1`, model/CUDA và ảnh `../test.jpeg` tự chuẩn bị với sự đồng ý của người trong ảnh. Xem [phạm vi và kết quả](TEST_REPORT.md).

## Thành phần chính

| Vị trí | Vai trò |
| --- | --- |
| `attendance_system/` | Cấu hình Django, routing, SQLite mặc định |
| `portal/models.py` | Sinh viên, môn/lớp, lịch, buổi, bản ghi, camera, thống kê |
| `portal/attendance.py` | Nghiệp vụ thống nhất, chống trùng, kiểm tra lớp/ngày/buổi |
| `portal/face_recognition.py` | OpenCV xử lý ảnh, InsightFace embedding, cosine matching |
| `portal/views.py` | Giao diện, JSON API, CSV, stream máy chủ |
| `portal/migrations/` | Schema và migration gộp bản ghi trùng |
| `portal/tests.py` | Kiểm thử nghiệp vụ, API, vision |
| `templates/`, `static/` | VISTA, chọn camera, nhãn tên/điểm tương đồng |
| `tests/` | Kiểm thử JavaScript bằng Node.js |

Database, ảnh, embedding, venv và báo cáo có dữ liệu thật chỉ lưu local, không commit. Portal/API chưa có phân quyền; chạy loopback cho demo, không public server. “Khớp …%” là điểm tương đồng, không phải xác suất chính xác.
