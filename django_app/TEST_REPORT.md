# Báo cáo kiểm thử VISTA

Ngày: 05/10/2026. Môi trường local: Windows, Python 3.12.10, Django 4.2.30, OpenCV 5.0.0, InsightFace 2.1, ONNX Runtime GPU 1.22.0, RTX 3050 Laptop.

## Kết quả

**46/46 test PASS**, bật test mô hình thật. Lần chạy lại trước commit: 3.846 giây. 41 test nghiệp vụ/API, 4 test vision/stream, 1 test tích hợp mô hình thực. SQLite test và thư mục embedding/ảnh tạm độc lập với dữ liệu đang dùng.

```powershell
$env:RUN_VISION_TESTS='1'
.\venv\Scripts\python.exe manage.py test portal --verbosity 1
```

```text
Found 46 test(s).
System check identified no issues (0 silenced).
..............................................
Ran 46 tests in 3.846s
OK
Destroying test database for alias 'default'...
```

`manage.py check`, `makemigrations --check --dry-run`, `node --check static/js/main.js`, `git diff --check` đều qua. Requirement lock trùng môi trường hiện tại (pip --dry-run --no-deps); setup PowerShell đã parse không lỗi. Chưa cài lại toàn bộ môi trường sạch trên máy thứ hai.

## Phạm vi tự động

| Nhóm | Đã kiểm tra |
| --- | --- |
| Trang | Tổng quan, quản lý, đăng ký, webcam, lịch, phiên, công nghệ, login Admin đều render |
| API đọc | Stats, students, attendance today, schedules, sessions, registered faces, system, session attendance |
| Ghi điểm danh | Lặp không trùng, giữ giờ vào, tách tự do/buổi, giờ địa phương và ranh giới ngày, điểm 0–100 hữu hạn |
| Đăng ký | ID/email/path/Windows reserved name, ảnh/base64/count không hợp lệ, không mặt/nhiều mặt, lưu nhiều ảnh/embedding, bảo vệ ID đã thuộc người khác |
| Nhận diện | Dict kết quả đúng cấu trúc, bbox/scale/cosine, unknown/identity không liên kết không ghi, dry-run, sai lớp không ghi |
| Buổi học | Tạo idempotent, đúng ngày/thứ, không mở lại buổi kết thúc, không ghi buổi cũ/đóng, kết thúc ghi vắng |
| Lịch | Tạo môn/lớp/lịch, gắn sinh viên cùng lớp, trùng tiết và bộ lọc sai bị từ chối |
| Hồ sơ | Đổi mã/họ tên/lớp, di chuyển identity, hỗ trợ tên legacy khác hoa/thường, duplicate không làm mất mặt, xóa đúng đối tượng |
| Identity xung đột | Họ tên giống mã người khác không lấy nhầm/xóa nhầm embedding/ảnh người khác |
| CSV | Theo buổi, UTF-8 BOM, escape công thức bảng tính |
| An toàn API | CSRF, sai method, JSON sai/array, ID không tồn tại, constraints DB chống trùng |
| Camera máy chủ | Không mở được trả 503; đọc lỗi hoặc client đóng stream thì release, không vòng lặp vô hạn |
| Django Admin | 8 module có thể truy cập bằng superuser trong testDB |
| Mô hình thực | Đăng ký ảnh test.jpeg, nhận diện lại đúng REAL01, điểm >95, ghi 1 bản, ảnh đen 0 mặt, detection và recognition thực có CUDAExecutionProvider |

Test cùng một ảnh đăng ký và nhận diện chỉ xác nhận tích hợp. Không dùng kết quả này để tuyên bố độ chính xác nhận diện ngoài đời.

## Kiểm tra trực tiếp trên Edge

- Tổng quan: số liệu thật 2 sinh viên, 1 người điểm danh, 0 buổi. Bản ghi trùng cũ không còn hiển thị hai lần.
- Quản lý: tìm kiếm không có kết quả, mở hồ sơ từ API, hủy chỉnh sửa, chuyển tab sinh viên/lịch sử/camera.
- Đăng ký: camera/upload tabs, hồ sơ thiếu ảnh báo lỗi; bật webcam, chụp mẫu cho preview 1/12, tắt webcam. Không lưu hồ sơ kiểm thử vào DB thật.
- Lịch: đổi thứ, mở/hủy dialog; khoảng tiết 3→1 bị API từ chối và hiển thị lỗi. Không tạo lịch thử trong DB thật.
- Điểm danh: anh xác nhận quyền camera. Webcam thực 1280×720, video readyState=4, đang phát; API xử lý khung hình trả 200 liên tiếp; nút dừng đưa về “Camera đã dừng”.
- Trong thời điểm webcam test chưa phát hiện khuôn mặt. Không coi đó là test xác minh một sinh viên đứng trước webcam đã được nhận đúng.
- Sau restart, test HTTP thật với ảnh local `test.jpeg`, CSRF và `record:false`: nhận diện đúng hồ sơ đã đăng ký, điểm tương đồng 99.4%, `recorded:false`; số bản ghi trước/sau vẫn 1/1. API system xác nhận provider đang dùng CUDA. Lượt đầu 3132.4 ms bao gồm tải/khởi tạo model, không phải tốc độ ổn định. Ảnh kiểm thử không được phân phối trong repo.
- Công nghệ: sau khi webcam chạy hiển thị OpenCV 5.0.0, InsightFace/buffalo_l và GPU/CUDA thực. Model được lazy-load lại sau mỗi restart.
- Django Admin: login đã được kiểm tra bố cục thật, không tạo/reset mật khẩu admin thật.
- Mobile 390×844: menu điều hướng hoạt động; home, lịch, register, scan, quản lý, technology không tràn trang ngang. Bảng rộng cuộn trong khung; lịch tuần cuộn riêng. Đã reset viewport về kích thước mặc định.
- Các thao tác sửa/xóa/lưu mặt thành công được kiểm thử trong testDB; không thực hiện xóa hồ sơ thật qua browser. Chọn file từ hộp thoại native chưa kiểm tra end-to-end; decoding/file validation và camera preview đã kiểm tra riêng.
- Trang phiên học đã render và kiểm thử API/nghiệp vụ; chưa tạo phiên giả trên DB thật chỉ để chụp màn hình.

## Lỗi đã sửa

- View cũ đọc sai tuple/dict từ đăng ký/nhận diện.
- Điểm tương đồng bị dùng sai đơn vị.
- Ghi điểm danh bị trùng và cập nhật giờ không phù hợp.
- Điểm danh tự do bị lẫn với phiên lớp.
- Timestamp filename có thể trùng, khiến hai ảnh ghi đè nhau: đổi sang UUID.
- Camera lỗi tiếp tục đọc vô hạn: dừng stream và release.
- Không kiểm tra người thuộc lớp, ngày/trạng thái buổi hoặc lịch trùng tiết.
- Số liệu mẫu hiển thị như số thực: đổi sang truy vấn database.
- Các API ghi thiếu CSRF/validation: đã bổ sung.
- Khóa mặt theo họ tên làm việc đổi tên/ID dễ mất liên kết: dùng mã sinh viên + hỗ trợ legacy.

## Dữ liệu được bảo toàn

Migration 0003 đã chạy sau sao lưu. Gộp **1 bản ghi điểm danh trùng** của dữ liệu cũ, giữ bản đầu và giờ vào sớm nhất; 2 sinh viên ban đầu giữ nguyên. Database trước sửa: `backups/db-before-vista-20261005.sqlite3`. Có thể phục hồi bằng bản sao khi server dừng; không phục hồi đè mà chưa xác định dữ liệu phát sinh mới.

Kho `face_database.pkl` và ảnh thật không bị test thay đổi. Các identity cũ không gắn hồ sơ sinh viên vẫn giữ, không tự ghi điểm danh cho identity không liên kết. Thời gian/điểm tương đồng lịch sử từ code cũ không tự “đoán” để sửa.

Metadata CPU ONNX Runtime đã gỡ còn sót `~nnxruntime-1.30.0.dist-info` được chuyển khỏi site-packages vào `backups/onnxruntime-uninstall-leftovers/`, không xóa vĩnh viễn. Runtime đang dùng là bản GPU.

## Giới hạn cần biết

- Chưa có liveness/chống dùng ảnh chụp.
- Chưa đo FAR/FRR hoặc đánh giá ảnh khác góc/ánh sáng trên tập độc lập.
- Portal/API chưa có xác thực và phân quyền như Django Admin; chỉ phục vụ demo localhost. Không public bản này.
- Chưa kiểm thử concurrent đa process/high load, MySQL, triển khai production, browser khác hoặc camera khác.
- InsightFace phát FutureWarning từ scikit-image khi căn chỉnh mặt; các test vẫn qua, không ẩn warning hoặc sửa thư viện trong venv.
- Ngưỡng 55% cần hiệu chỉnh bằng dữ liệu đánh giá; không phải “độ chính xác 55%”.

## Bổ sung chọn webcam laptop — 05/10/2026

- Windows nhận ACER HD User Facing và Iriun Webcam, cả hai không báo lỗi thiết bị.
- Thêm bộ chọn và tải lại danh sách camera ở đăng ký, điểm danh tự do và phiên học; ưu tiên webcam tích hợp, không chọn Iriun theo thứ tự thiết bị mặc định.
- 11/11 Node tests về chính sách chọn thiết bị qua: native đứng sau Iriun, lưu lựa chọn vật lý, không dùng camera ảo tự động, thiết bị mất/ẩn nhãn, explicit ID và không thu âm.
- Test Edge thực: mở đúng track ACER HD User Facing (04f2:b76f), video 1280×720, readyState=4, không pause; API nhận diện tiếp tục trả kết quả. Dừng xong giải phóng camera và giữ ACER trong danh sách chọn.
- Không thay đổi driver, không gỡ Iriun hay sửa cài đặt Windows. Mẫu hình chỉ xử lý cục bộ khi bắt đầu điểm danh; kiểm tra lựa chọn không tạo hồ sơ sinh viên.

Ảnh giao diện được giữ trong tài liệu local, không đưa lên repo vì có dữ liệu người dùng thật.

## Bổ sung nhãn ngay trên khuôn mặt — 05/10/2026

- Tên, điểm tương đồng “Khớp …%”, mã sinh viên và trạng thái được hiển thị ngay sát khung mặt trên camera; không cần cuộn xuống để xem kết quả. Dùng điểm thật từ API, không diễn giải thành xác suất chính xác.
- Nhãn HTML giữ cỡ chữ 14px thay vì bị thu nhỏ theo canvas; căn theo vùng video/ảnh `object-fit: contain`, tự dịch vào trong khi sát mép và tránh thanh thông tin camera. Đổi kích thước thì tính lại vị trí. Áp dụng cho điểm danh tự do, buổi học và kiểm tra ảnh.
- API trả thêm kích thước ảnh thực đã xử lý, để tọa độ trên ảnh upload vẫn đúng khi backend giảm kích thước ảnh. Test Django xác nhận các trường kích thước.
- 21/21 Node tests qua: 11 test chọn camera, 10 test nhãn/letterbox/các góc/mobile/trạng thái/điểm 0 và dữ liệu không hợp lệ. Kiểm tra cú pháp hai script và `manage.py check` đều qua.
- Edge thực, buổi học đang sử dụng: ACER HD User Facing 1280×720, readyState=4; nhận đúng hồ sơ đã đăng ký và hiển thị điểm khớp thay đổi theo khung hình cùng “Đã điểm danh”. Nhãn nằm trong vùng video ở desktop và viewport 390×844; tên vẫn 14px, trang không tràn ngang.
- Bấm dừng: nhãn còn 0, canvas/video ẩn, video paused=true/readyState=0. Bật lại thành công; giữ camera đang chạy theo trạng thái sử dụng ban đầu. Không mở/đóng buổi, không tạo hồ sơ hoặc sửa bản ghi của anh để kiểm thử giao diện.
- Trạng thái người lạ/sai lớp và nhãn sát cả bốn góc được kiểm thử tự động; chưa làm người lạ đứng trước webcam để xác minh UI trực tiếp.

Ảnh webcam minh họa nhãn tên/điểm tương đồng được giữ local, không đưa lên repo.

## Kiểm tra trước commit — 05/10/2026

- 46/46 Django tests qua, có test mô hình GPU thực; 21/21 Node tests qua.
- `manage.py check`, `makemigrations --check --dry-run` và kiểm tra cú pháp ba file JavaScript chính đều qua.
- Server local đã được dừng trước khi chạy test GPU. Không sửa database/ảnh/embedding đang sử dụng.
- Database, kho ảnh/embedding, Python cache và ảnh test cũ được bỏ khỏi Git index, giữ nguyên file trên máy. `.gitignore` ngăn đưa lại các file này vào commit mới.
- Báo cáo DOCX và ảnh giao diện có dữ liệu thật chỉ giữ local, không đưa lên repo. Dữ liệu từng commit trong lịch sử Git không bị xóa bởi thay đổi này; không rewrite lịch sử hoặc force-push.
