# Báo cáo công việc hằng ngày từ Linear

> Đọc Linear, cho AI tóm bình luận, gửi Telegram — chạy tự động hoàn toàn trên GitHub Actions.
> Không cần máy nào bật liên tục, không cần cài đặt gì trên máy Linux.

---

## 1. Một lượt chạy đi những đâu

```
GitHub Actions (lịch cron 8h50 và 18h00 giờ VN, thứ Hai đến thứ Sáu)
   → bao_cao.py hỏi Linear: đợt sprint đang chạy là đợt nào
   → kéo về tối đa 200 việc, mỗi việc kèm 20 bình luận mới nhất
   → mã lọc và xếp việc (phần này KHÔNG có AI)
   → DeepSeek đọc cả chuỗi bình luận của từng việc sắp in, trả tiến độ + vướng mắc
   → mã đem tiến độ so với mốc lượt trước trong moc_tien_do.json
   → mã ghép chữ thành tin nhắn
   → đẩy sang cửa nhận n8n
   → n8n gửi Telegram: nhóm team + riêng Thanh
```

**Chỗ nào là mã, chỗ nào là AI**

| Bước | Ai làm | Ghi chú |
|---|---|---|
| Tìm sprint, kéo việc, lọc, xếp, ghép chữ | Mã | Tất định, không đoán |
| Đọc bình luận → tiến độ + vướng mắc | AI (DeepSeek, `deepseek-chat`) | Mỗi việc một lượt gọi, chỉ gọi cho việc sắp in ra |
| So tiến độ với lượt trước | Mã | Đọc `moc_tien_do.json`, không để AI đoán |
| Gửi Telegram | n8n | Luồng `Claude → Telegram: Báo cáo công việc`, id `L4dspyvjdXlbTLpI` |

AI hỏng thì mã tự lùi về đọc phần trăm thẳng từ bình luận mới nhất. Báo cáo không bao giờ trống.

---

## 2. Hai bản báo cáo

| Bản | Giờ | Nội dung | Dòng phụ dưới mỗi việc |
|---|---|---|---|
| Đầu ngày | 8h50 | Chỉ việc đang làm dở | **Không có dòng nào.** Chỉ tên việc, trạng thái, phần trăm |
| Cuối ngày | 18h00 | Việc xong trong ngày + việc có bình luận trong ngày, gộp chung | Chênh lệch nằm ngay trên dòng trạng thái; dưới đó chỉ dòng ❗ vướng mắc khi có |

**Bản cuối ngày, ba dạng con số ở cuối dòng trạng thái:**

| Dạng | Khi nào |
|---|---|
| `10% → 40%` | Con số đổi so với lượt gửi trước |
| `40% (không có thay đổi)` | Con số đứng yên qua ít nhất một lượt trước đó |
| `40%` | Chưa có mốc cũ để so, ví dụ lượt chạy đầu tiên |

Cả hai đều **gom theo người**, không tách mục theo trạng thái. Trong một người: việc xong xếp trước, rồi tới việc ưu tiên cao.

---

## 3. Luật đã chốt, đừng sửa lại

| Luật | Chốt ngày |
|---|---|
| Bản đầu ngày **không in dòng phụ nào**. Cái gì nhìn phần trăm là biết thì không giải thích lại | 19/08 |
| Bản cuối ngày in **chênh lệch so với lượt trước**, không in câu tóm chung chung | 19/08 |
| Mốc so sánh do **mã** tự lưu, cấm để AI suy ra con số của lần trước | 19/08 |
| Dòng ❗ chỉ in khi bình luận **nêu rõ** vướng mắc; không có gì thì không nói gì | 19/08 |
| Lịch bản đầu ngày chạy **8h50**, không phải 9h00 | 19/08 |
| Bình luận phải được AI đọc **cả chuỗi** | 15/08 |
| Tiến độ đọc từ bình luận mà ra, dù ghi bằng số hay bằng chữ. Không thấy thì ghi "chưa cập nhật", **cấm đoán** | 15/08 |
| AI cấm mô tả lại tiến độ bằng lời và cấm nhắc lại con số phần trăm | 15/08, siết thêm 19/08 |
| Gom theo người, không gom theo trạng thái | 15/08 |
| Việc xong chỉ lấy đúng trong ngày, không lấy vòng 24 tiếng | 14/08 |
| Đọc cả Backlog: việc ở Backlog có bình luận trong 7 ngày vẫn đưa vào, kèm dòng nhắc chuyển sang In Progress | 14/08 |
| Lấy 20 bình luận **mới nhất**, không phải 5 cái cũ nhất | 14/08 |
| Bỏ hẳn mục "đang làm nhưng im lặng" | 14/08 |
| Bỏ hẳn dòng đếm số ngày không ai bình luận | 19/08 |
| Tên việc đã tự mang nhãn trong ngoặc vuông thì không gắn thêm nhãn máy đoán | 14/08 |
| Chỉ đếm bình luận, **không đếm mốc sửa của Linear** (mốc sửa bị kéo hàng loạt thì vô nghĩa) | 14/08 |

---

## 4. Cài đặt — chỉ làm một lần

Tất cả nằm trong GitHub, không cần máy Linux nào chạy nền.

1. **Đẩy repo này lên GitHub** (repo riêng tư).
2. Vào repo → **Settings → Secrets and variables → Actions → New repository secret**, tạo đúng 5 secret:

   | Tên | Giá trị |
   |---|---|
   | `LINEAR_KEY` | Linear → Settings → API → Personal API key |
   | `WEBHOOK` | `https://n8n.kfsp.vn/webhook/kfsp-daily-report-telegram` |
   | `MODEL_URL` | `https://api.deepseek.com/chat/completions` |
   | `MODEL_KEY` | Khoá DeepSeek, lấy từ máy kf-data-agent |
   | `MODEL_TEN` | `deepseek-chat` |

3. Vào tab **Actions**, bật workflow "Bao cao cong viec" nếu GitHub hỏi (`Enable workflow`).
4. Test bằng tay: **Actions → Bao cao cong viec → Run workflow**, chọn `sang`/`cuoi-ngay`, để `thu = true` (chỉ in ra log, không gửi Telegram).

Xong bước 4 thấy đúng người đúng việc là xong — lịch cron sẽ tự chạy 8h50 và 18h00 giờ VN, thứ Hai đến thứ Sáu, không cần làm gì thêm.

**Sửa mã sau này:** sửa `bao_cao.py`, commit, push lên `main` — lần chạy tiếp theo tự dùng bản mới. Không còn bước `scp` hay đồng bộ nhiều máy nào nữa.

⚠️ GitHub tự tắt lịch cron nếu repo không có commit nào trong 60 ngày. Gặp trường hợp đó, vào **Actions → Bao cao cong viec → bấm "Enable workflow"** lại là chạy tiếp.

---

## 5. Chạy thử trên máy mình (tuỳ chọn, chỉ để xem trước khi push)

```bash
cp .env.mau .env      # rồi điền LINEAR_KEY, MODEL_KEY thật vào .env
python3 bao_cao.py --sang --thu        # chỉ in ra màn hình, KHÔNG gửi
python3 bao_cao.py --cuoi-ngay --thu
```

`.env` bị `.gitignore` chặn, không bao giờ lên kho. Trên Windows dùng `py` thay cho `python3`:

```powershell
cp .env.mau .env
py bao_cao.py --sang --thu
```

Bỏ `--thu` là gửi thật — chỉ bỏ khi đã xem log và chắc đúng.

---

## 6. Tệp mốc tiến độ

`moc_tien_do.json` nằm ngay trong repo (workflow tự commit lại sau mỗi lượt gửi thật). Mỗi mã việc giữ ba ô: phần trăm lượt gần nhất, giờ của lượt đó, và giờ con số hiện tại bắt đầu đứng yên. **Chỉ lượt gửi thật mới ghi tệp này**, chạy `--thu` bao nhiêu lần cũng không làm lệch. Xoá tệp thì hai lượt sau mới có mốc để so lại.

---

## 7. Hai bot Telegram — đừng lẫn

| Bot | Tên | Việc | Cho ai |
|---|---|---|---|
| `kfagent_01_bot` | kf-agent-1 | AI coworker, trao đổi riêng với Thanh | **Chỉ Thanh** (`5042181993`), khoá theo danh sách cho phép |
| `dstv_ctck_bot` | Tech-KFSP | Gửi báo cáo công việc | Nhóm team (`-1001863491856`) + Thanh |

Muốn hỏi ý Thanh giữa chừng thì dùng bot AI coworker, đừng bắn vào nhóm team.

---

## 8. Còn treo

- Nếu trước đây có cài crontab chạy `bao_cao.py` trên một máy Linux nào đó (mô hình cũ), **phải tắt hẳn** trước khi bật lịch GitHub Actions ở đây, không thì mỗi lượt sẽ gửi trùng hai lần.
- Bản sáng phát hiện **thiếu người** (ai không có việc nào) thì nhắn riêng Thanh qua bot AI coworker, đề xuất việc cho người đó theo mức ưu tiên. **Chưa viết mã.** Chờ Thanh chốt: danh sách người phải có mặt · nguồn lấy việc đề xuất · máy chỉ đề xuất hay tự gán người trên Linear.
