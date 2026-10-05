# VISTA — Hệ thống điểm danh bằng nhận diện khuôn mặt

Ứng dụng điểm danh sử dụng **Django, OpenCV và InsightFace**, với giao diện tiếng Việt, webcam trình duyệt, quản lý sinh viên và điểm danh theo buổi học.

> Bản hiện tại phục vụ phát triển và demo local. Portal/API chưa có xác thực, phân quyền như Django Admin; chỉ chạy tại `127.0.0.1`, không công khai server ra Internet hoặc LAN.

## Mục lục

- [Chức năng](#chức-năng)
- [Kiến trúc và công nghệ](#kiến-trúc-và-công-nghệ)
- [Cài đặt và chạy](#cài-đặt-và-chạy)
- [Hướng dẫn sử dụng](#hướng-dẫn-sử-dụng)
- [Cấu trúc dự án](#cấu-trúc-dự-án)
- [API](#api)
- [Dữ liệu và sao lưu](#dữ-liệu-và-sao-lưu)
- [Kiểm thử](#kiểm-thử)
- [Xử lý sự cố](#xử-lý-sự-cố)
- [Giới hạn hiện tại](#giới-hạn-hiện-tại)

## Chức năng

| Giao diện | Đường dẫn | Chức năng |
| --- | --- | --- |
| Tổng quan | `/` | Thống kê từ database, hoạt động gần đây, xuất CSV |
| Lịch học | `/schedule/` | Xem lịch tuần, tạo lịch, mở buổi học hôm nay |
| Điểm danh theo buổi | `/session/<id>/` | Nhận diện sinh viên thuộc lớp, theo dõi danh sách, kết thúc buổi |
| Điểm danh trực tiếp | `/scan/camera/` | Webcam hoặc ảnh, ghi điểm danh tự do trong ngày |
| Đăng ký khuôn mặt | `/register/` | Chụp webcam hoặc tải ảnh, lưu hồ sơ và mẫu khuôn mặt |
| Quản lý sinh viên | `/admin-dashboard/` | Tìm/lọc, sửa/xóa hồ sơ, xem lịch sử và camera |
| Về hệ thống | `/technology/` | Công nghệ, ngưỡng so khớp, trạng thái model và GPU/CPU thực tế |
| Django Admin | `/admin/` | Đăng nhập quản trị sinh viên, môn/lớp, lịch, buổi, bản ghi, camera, thống kê |

Các điểm chính:

- Hiển thị **tên, mã sinh viên, điểm “Khớp …%” và trạng thái ngay trên khung khuôn mặt**.
- Chọn thiết bị camera, tải lại danh sách, ưu tiên webcam vật lý; không tự chuyển sang Iriun/camera ảo. Không thu âm.
- Chống trùng: một bản ghi tự do/sinh viên/ngày và một bản ghi/sinh viên/buổi. Quét lại giữ giờ vào đầu tiên.
- Kiểm tra lớp, ngày và trạng thái buổi trước khi ghi; kết thúc buổi ghi vắng cho sinh viên chưa điểm danh.
- Đăng ký 1–12 ảnh JPG/PNG, tối đa 8 MB/ảnh; chỉ lưu ảnh có đúng một khuôn mặt. Identity dùng mã sinh viên thay vì họ tên.
- CSV UTF-8 BOM, xử lý ô có thể bị diễn giải thành công thức bảng tính.
- Giao diện responsive desktop/điện thoại; frontend không cần bước build Node.js.

## Kiến trúc và công nghệ

```text
Webcam / ảnh tải lên
        ↓
Trình duyệt: getUserMedia, chọn camera, gửi ảnh bằng HTTP cục bộ
        ↓
Django API → OpenCV giải mã / thay đổi kích thước ảnh
        ↓
InsightFace buffalo_l → phát hiện mặt và tạo embedding
        ↓
NumPy cosine similarity → so khớp mẫu theo mã sinh viên
        ↓
Kiểm tra nghiệp vụ → SQLite lưu điểm danh → giao diện vẽ khung / nhãn
```

OpenCV đảm nhiệm xử lý ảnh và hỗ trợ camera/stream máy chủ. **Engine phát hiện và tạo đặc trưng khuôn mặt là InsightFace**, chạy qua ONNX Runtime; không phải thuật toán nhận diện thuần OpenCV. Webcam VISTA do trình duyệt mở, không phải `cv2.VideoCapture` trên trình duyệt.

Ngưỡng cosine hiện tại là `0.55`, cấu hình tại [`portal/face_recognition.py`](django_app/portal/face_recognition.py). Điểm “Khớp …%” là điểm tương đồng, **không phải xác suất nhận diện đúng hay độ chính xác đo trên tập kiểm thử**.

Môi trường đã kiểm thử:

| Thành phần | Phiên bản / cấu hình |
| --- | --- |
| Hệ điều hành | Windows x64 |
| Python | 3.12.10 |
| Django | 4.2.30 |
| OpenCV (`opencv-python`) | 5.0.0.93 |
| InsightFace | 2.1, model `buffalo_l` |
| ONNX Runtime GPU | 1.22.0 |
| GPU | NVIDIA RTX 3050 Laptop |
| Database mặc định | SQLite |
| Múi giờ | `Asia/Ho_Chi_Minh` |

Dependency được chốt trong [`requirements.txt`](django_app/requirements.txt). Bộ cài đã kiểm thử cho **Windows/Python 3.12/GPU NVIDIA**, không phải bộ cài đa nền tảng.

## Cài đặt và chạy

### 1. Chuẩn bị

- Git, Python 3.12 x64 có Python Launcher (`py`), PowerShell.
- Driver NVIDIA phù hợp cho bản GPU. DLL CUDA/cuDNN được cài trong venv bằng các dependency NVIDIA.
- Kết nối mạng để tải dependency và model lần đầu.
- Trình duyệt hỗ trợ webcam; cấp quyền camera cho `http://127.0.0.1:8000`.
- Node.js chỉ cần cho kiểm thử JavaScript, không cần để chạy website.

### 2. Clone và cài môi trường

Mở PowerShell:

```powershell
git clone https://github.com/ThangvanOwO/nhan_dien_khuon-_mat_v2.git nhan_dien_khuon_mat
cd nhan_dien_khuon_mat\django_app
powershell -NoProfile -ExecutionPolicy Bypass -File .\setup_windows.ps1
```

Script tạo `django_app/venv` nếu chưa có và cài dependency trong venv; không xóa database, ảnh hoặc embedding. Dừng server trước khi cập nhật môi trường.

Cài thủ công, từ thư mục `django_app`:

```powershell
py -3.12 -m venv venv
.\venv\Scripts\python.exe -m pip install --no-deps -r requirements.txt
.\venv\Scripts\python.exe manage.py check
```

**Giữ `--no-deps`**: dependency đã được liệt kê đầy đủ, tránh InsightFace kéo thêm distribution ONNX Runtime CPU và ghi đè module GPU. Không cài đồng thời `onnxruntime` và `onnxruntime-gpu` trong cùng venv. Nếu script báo đã có CPU runtime, xử lý distribution đó trong venv dự án trước khi chạy lại; không gỡ thư viện toàn hệ thống.

`pip check` có thể báo InsightFace thiếu distribution CPU, dù bản GPU cung cấp cùng module `onnxruntime`. Không cài thêm CPU chỉ để xóa cảnh báo này; xem provider thực tại `/technology/` sau khi nhận diện.

### 3. Tạo database và tài khoản quản trị

```powershell
.\venv\Scripts\python.exe manage.py migrate
.\venv\Scripts\python.exe manage.py createsuperuser
```

Migrations có sẵn; không cần `makemigrations` khi cài lần đầu. Database mới không kèm sinh viên, ảnh hoặc tài khoản mẫu. `createsuperuser` cho phép tự đặt tài khoản/mật khẩu; không có mật khẩu mặc định.

### 4. Khởi động

```powershell
.\venv\Scripts\python.exe manage.py runserver 127.0.0.1:8000 --noreload
```

Mở **[http://127.0.0.1:8000/](http://127.0.0.1:8000/)**. Dùng HTTP và cổng 8000, không dùng `https://127.0.0.1/`. Dừng bằng **Ctrl+C** trong terminal đang chạy.

Model được lazy-load khi đăng ký/nhận diện lần đầu; có thể tải vào `%USERPROFILE%\.insightface\models\buffalo_l`. Lượt khởi tạo thường lâu hơn lượt tiếp theo. Trước khi model được nạp, giao diện chưa thể xác nhận provider đang thực thi.

Máy không có GPU cần môi trường CPU riêng: dùng `onnxruntime` thay cho `onnxruntime-gpu`, bỏ dependency `nvidia-*`. Cấu hình CPU riêng chưa được kiểm thử đầy đủ; không dùng nguyên bộ GPU lock như hướng dẫn CPU đã xác minh.

## Hướng dẫn sử dụng

### Đăng ký sinh viên

1. Mở `/register/`, nhập mã sinh viên, họ tên, lớp và email nếu có.
2. Chọn webcam hoặc tải ảnh. Khuyến nghị 3–5 ảnh rõ, thay đổi góc mặt/ánh sáng vừa phải, mỗi ảnh chỉ có một khuôn mặt.
3. Kiểm tra preview rồi lưu. Mã tồn tại chỉ nhận thêm mẫu khi họ tên trùng hồ sơ; đổi thông tin bằng trang quản lý.

### Điểm danh tự do

1. Mở `/scan/camera/`, chọn webcam laptop, cấp quyền và bấm bắt đầu.
2. Khi khớp hồ sơ, tên/điểm tương đồng/trạng thái hiện trên khung và danh sách cập nhật.
3. Bấm dừng để giải phóng camera. Có thể kiểm tra bằng ảnh thay webcam.

Camera ảo chỉ dùng khi chủ động chọn. Dừng camera trước khi đổi thiết bị; bấm **Tải lại** khi cắm thêm camera. Lựa chọn camera vật lý được nhớ trong trình duyệt.

### Điểm danh theo buổi

1. Tạo lịch tại `/schedule/` với môn, lớp, thứ, tiết và phòng. Sinh viên có `class_name` trùng mã lớp được liên kết khi tạo lịch/đồng bộ hồ sơ; có thể quản lý thành viên lớp trong Django Admin.
2. Mở lịch đúng hôm nay để bắt đầu; không mở lại buổi đã kết thúc.
3. Nhận diện tại `/session/<id>/`. Người ngoài lớp không được ghi vào buổi.
4. Kết thúc buổi để ghi vắng cho người chưa có bản ghi; xuất CSV để tổng hợp.

### Quản lý và tra cứu

`/admin-dashboard/` hỗ trợ tìm/lọc sinh viên, sửa hồ sơ, lịch sử và camera. Xóa sinh viên đồng thời xóa lịch sử, embedding và ảnh liên quan: **sao lưu trước khi xóa**. Đổi mã qua API/giao diện di chuyển identity tương ứng; không tự đổi tên thư mục ảnh bằng tay.

## Cấu trúc dự án

```text
nhan_dien_khuon_mat/
├── README.md
├── .gitignore
├── django_app/
│   ├── manage.py
│   ├── requirements.txt
│   ├── setup_windows.ps1
│   ├── README.md
│   ├── TEST_REPORT.md
│   ├── attendance_system/       # Settings, URLs, ASGI/WSGI
│   ├── portal/
│   │   ├── models.py           # Sinh viên, lớp, lịch, buổi, điểm danh
│   │   ├── attendance.py       # Nghiệp vụ điểm danh thống nhất
│   │   ├── face_recognition.py # OpenCV, InsightFace, kho embedding
│   │   ├── views.py            # Trang, API, CSV
│   │   ├── urls.py
│   │   ├── admin.py
│   │   ├── migrations/
│   │   └── tests.py
│   ├── templates/              # Giao diện VISTA và Django Admin
│   ├── static/                 # CSS, JavaScript, favicon
│   └── tests/                  # Node tests camera / nhãn khuôn mặt
├── project.py                  # Prototype desktop cũ, không phải entry point VISTA
└── register_viet.py            # Script thử nghiệm cũ, không thuộc luồng cài đặt
```

File/thư mục local tự sinh hoặc riêng tư không đưa vào mã nguồn: venv, SQLite, `face_database.pkl`, `my_faces/`, media, backup, ảnh test và báo cáo có ảnh người dùng.

## API

API trả JSON, trừ export CSV và video stream. API ghi nhận JSON; `POST`/`PUT`/`DELETE` cần CSRF cookie và header `X-CSRFToken`. Mở trang VISTA trước để nhận cookie; CSRF **không thay thế xác thực người dùng**.

| Method | Endpoint | Nội dung |
| --- | --- | --- |
| GET | `/api/stats/` | Thống kê ngày hiện tại |
| GET | `/api/students/` | Danh sách hồ sơ |
| GET | `/api/attendance/today/` | Điểm danh hôm nay, gồm tự do và theo buổi |
| POST | `/api/register-face/` | `student_id`, `full_name`, `class_name`, `email?`, `images[]` |
| POST | `/api/recognize-face/` | `image`, `session_id?`, `record?` |
| POST | `/api/record-attendance/` | `student_id`, `confidence` (0–100), `camera_id?` |
| GET | `/api/registered-faces/` | Identity, số embedding, hồ sơ liên kết |
| PUT | `/api/update-student/<pk>/` | Sửa hồ sơ; `<pk>` là ID database, không phải mã sinh viên |
| DELETE | `/api/delete-student/<pk>/` | Xóa hồ sơ và dữ liệu liên quan |
| GET/POST | `/api/schedules/` | Danh sách/tạo lịch; GET có `?day=0..6` |
| POST | `/api/session/create/` | `schedule_id`, `date?` (`YYYY-MM-DD`, phải là hôm nay) |
| POST | `/api/session/record/` | `session_id`, `student_id`, `confidence` |
| GET | `/api/sessions/today/` | Các buổi trong ngày |
| GET | `/api/session/<id>/attendance/` | Danh sách điểm danh của buổi |
| GET | `/api/attendance/export/?date=YYYY-MM-DD` | CSV của ngày; mặc định hôm nay |
| GET | `/api/attendance/export/?session=<id>` | CSV của buổi |
| GET | `/api/system/` | Phiên bản, model, provider khả dụng/đang dùng, thời gian xử lý |

Ảnh trong JSON là base64 hoặc data URL JPG/PNG, không phải multipart upload. `record:false` cho phép nhận diện thử mà không ghi điểm danh.

Ví dụ nhận diện không ghi dữ liệu:

```json
{
  "image": "data:image/jpeg;base64,...",
  "record": false
}
```

API nhận diện trả `faces_detected`, `recognized[]` (tên, điểm tương đồng, bbox, mã sinh viên, trạng thái ghi), `image_width`, `image_height`, `scan_ms`, `threshold` trong `data`. Kích thước dùng để căn nhãn theo ảnh đã xử lý.

Ví dụ ghi điểm danh tự do cho hồ sơ đã tồn tại:

```json
{
  "student_id": "DEMO001",
  "confidence": 87.5,
  "camera_id": "BROWSER"
}
```

Response gồm `success`, `message` và `data`: `student_id`, `student_name`, `class_name`, `date`, `time_in`, `status`, `confidence`, `session_id`, `created`, cùng trường `time` tương thích. `created:false` nghĩa là đã có bản ghi, không tạo thêm.

Tạo lịch cần `subject_code`, `subject_name`, `class_id`, `day_of_week` (0 = Thứ Hai, 6 = Chủ Nhật), `start_period`, `end_period` (1–10), `room?`. Khoảng tiết đảo ngược hoặc trùng lịch cùng lớp bị từ chối.

`avg_scan_time` trong stats được giữ để tương thích: hiện là **thời gian lượt xử lý gần nhất tính bằng giây**, chưa phải trung bình/FPS. Chưa quét trả `null`. `active_cameras` dựa trên trạng thái hồ sơ camera trong database, không phải số webcam đang phát.

Route stream máy chủ: `GET /video_feed/` và `GET /session/<id>/video_feed/`. Đây là camera máy chủ, khác webcam trình duyệt của VISTA; chỉ dùng khi cần tích hợp tương ứng.

## Dữ liệu và sao lưu

| Vị trí local | Nội dung |
| --- | --- |
| `django_app/db.sqlite3` | Hồ sơ, lớp, lịch, buổi, điểm danh, tài khoản Django |
| `face_database.pkl` | Embedding theo identity/mã sinh viên |
| `my_faces/<student_id>/` | Ảnh đăng ký |
| `django_app/media/` | Media nếu được sử dụng |
| `django_app/backups/` | Sao lưu local |

Clone mới bắt đầu với dữ liệu trống. `migrate` tạo SQLite; đăng ký tạo kho ảnh/embedding. Giữ database, embedding và ảnh cùng một bộ sao lưu để tránh mất liên kết.

Trước nâng cấp dữ liệu cũ, dừng server và sao lưu các vị trí trên. Migration `0003_attendance_uniqueness` gộp điểm danh trùng trước khi thêm ràng buộc duy nhất, giữ giờ vào sớm nhất; rollback migration không phục hồi các bản trùng đã gộp. Không phục hồi đè lên dữ liệu mới nếu chưa sao lưu.

Chỉ nạp pickle do hệ thống tin cậy tạo; không tải `face_database.pkl` không rõ nguồn gốc. Không đưa database, ảnh, embedding hay tài liệu chứa dữ liệu thật vào Git. `.gitignore` không xóa dữ liệu đã nằm trong các commit lịch sử.

## Kiểm thử

Từ thư mục `django_app`:

```powershell
.\venv\Scripts\python.exe manage.py check
.\venv\Scripts\python.exe manage.py makemigrations --check --dry-run
.\venv\Scripts\python.exe manage.py test portal
node --test tests/camera-policy.test.cjs tests/face-overlay.test.cjs
```

Bộ Django gồm 46 test; mặc định bỏ qua 1 test mô hình thực. Test thường dùng mô hình giả lập, SQLite test và kho ảnh/embedding tạm, không sửa dữ liệu sinh viên đang sử dụng. Bộ Node gồm 21 test chọn camera và nhãn/geometry khuôn mặt.

Để chạy test tích hợp GPU thực:

1. Chuẩn bị JPG của người đồng ý cho kiểm thử, có đúng một khuôn mặt rõ, đặt tại `test.jpeg` ở root repo. Ảnh được Git bỏ qua, không cung cấp sẵn trong clone mới.
2. Đảm bảo model/CUDA hoạt động; dừng server để tránh chạy đồng thời với webcam.
3. Chạy:

```powershell
$env:RUN_VISION_TESTS = '1'
.\venv\Scripts\python.exe manage.py test portal
Remove-Item Env:\RUN_VISION_TESTS
```

Test thực xác minh đăng ký, nhận diện lại, ghi một bản điểm danh, ảnh không có mặt và provider CUDA của detection/recognition. Dùng cùng ảnh đăng ký và nhận diện chỉ kiểm tra tích hợp, **không chứng minh độ chính xác ngoài đời**. Chi tiết: [`TEST_REPORT.md`](django_app/TEST_REPORT.md).

## Xử lý sự cố

| Hiện tượng | Kiểm tra / xử lý |
| --- | --- |
| `ERR_CONNECTION_REFUSED` | Server đang chạy? Mở đúng `http://127.0.0.1:8000/`, không dùng HTTPS/cổng mặc định |
| Không mở được webcam | Cấp quyền trình duyệt/Windows, chọn camera vật lý, đóng app đang giữ camera, tải lại danh sách |
| Mở nhầm Iriun | Chủ động chọn webcam laptop; giao diện không tự dùng camera ảo làm fallback |
| Lần nhận diện đầu chậm | Model tải/khởi tạo; kiểm tra mạng/thư mục model, so sánh lượt tiếp theo |
| CUDA không hoạt động | Xem provider thực sau nhận diện tại `/technology/`, kiểm tra driver/dependency venv; không cài CPU chồng GPU |
| API trả CSRF 403 | Lấy cookie từ VISTA, gửi `X-CSRFToken` và cookie cùng origin |
| Không nhận ra sinh viên | Mẫu rõ, mã/liên kết hồ sơ, ánh sáng/khoảng cách; không giảm ngưỡng chỉ để ép nhận đúng |
| Không mở được buổi | Kiểm tra ngày/thứ, trạng thái kết thúc và thành viên lớp |

## Giới hạn hiện tại

- Chưa có liveness/chống dùng ảnh chụp hoặc video giả.
- Chưa đo FAR/FRR hay đánh giá góc mặt/ánh sáng trên tập độc lập.
- Portal/API chưa có xác thực và phân quyền; Django Admin có đăng nhập riêng. CSRF/validation không biến demo thành hệ thống production an toàn.
- Settings dùng `DEBUG=True`, secret key mẫu, `ALLOWED_HOSTS=['*']`; phải thay cấu hình và bổ sung bảo vệ trước khi công khai. Không dùng `runserver` cho production.
- Model có `late`, `time_out`, nhưng chưa tự tính đi muộn hoặc check-out tự động.
- Camera hoạt động là dữ liệu cấu hình, chưa có heartbeat thiết bị.
- SQLite là cấu hình đã kiểm thử. MySQL chưa được kiểm thử; dependency không kèm MySQL driver và unique constraint có điều kiện cần rà soát khi đổi database.
- Chưa kiểm thử đa process, tải lớn hoặc môi trường CPU/macOS/Linux sạch.

Mô hình pretrained không được phân phối trong repo. Tham khảo tài liệu và điều kiện model tại [InsightFace](https://github.com/deepinsight/insightface); tài liệu kỹ thuật: [OpenCV](https://docs.opencv.org/), [Django](https://docs.djangoproject.com/en/4.2/), [ONNX Runtime CUDA](https://onnxruntime.ai/docs/execution-providers/CUDA-ExecutionProvider.html).
