#!/usr/bin/env python3
# Bao cao cong viec team KFSP tu Linear, gui vao Telegram qua n8n.
#
# Chay tu dong tren GitHub Actions (xem .github/workflows/bao-cao.yml).
# Khong can may nao chay lien tuc — GitHub tu goi theo lich cron.
#
# 🔴 Khac ban Claude o ba cho, deu la sua loi chu khong phai doi y:
#   1. Ten dot sprint tren Linear la kieu My "Sprint MM/DD-MM/DD/YYYY".
#      Ban dan viec cu ghi DD/MM -> doc ra "thang 15", khong ton tai.
#      Chua lo ra vi hien chi co dung MOT dot sprint.
#   2. Lay binh luan cua tat ca viec trong MOT luot goi, khong goi tung viec.
#   3. Goi thang cua nhan n8n. Khong bi chan nhu moi truong lich chay Claude.
#
# Chay:
#   python3 bao_cao.py --sang        # bao cao sang: chi viec dang lam
#   python3 bao_cao.py --cuoi-ngay   # bao cao cuoi ngay: xong hom nay + dang lam
#   python3 bao_cao.py --sang --thu  # in ra man hinh, KHONG gui
import argparse
import json
import os
import re
import sys
import urllib.request
from datetime import datetime, timedelta, timezone

NHA = os.path.dirname(os.path.abspath(__file__))
GIO_VN = timezone(timedelta(hours=7))
MA_NHOM = "55909a3e-60d1-47cb-8b4e-6527795f559b"  # team "Kfsp Team"
LINEAR_URL = "https://api.linear.app/graphql"


# ─────────── cau hinh
def doc_env():
    ra = {}
    p = os.path.join(NHA, ".env")
    if os.path.exists(p):
        for dong in open(p, encoding="utf-8"):
            dong = dong.strip()
            if not dong or dong.startswith("#") or "=" not in dong:
                continue
            k, v = dong.split("=", 1)
            ra[k.strip()] = v.strip().strip('"').strip("'")
    for k in ("LINEAR_KEY", "WEBHOOK", "TOM_TAT", "MODEL_URL", "MODEL_KEY", "MODEL_TEN"):
        if os.environ.get(k):
            ra[k] = os.environ[k]
    return ra


CAU_HINH = doc_env()


# ─────────── goi Linear
def linear(truy_van, bien=None):
    khoa = CAU_HINH.get("LINEAR_KEY", "")
    if not khoa:
        sys.exit("Thieu LINEAR_KEY trong .env — vao Linear > Settings > API > Personal API key")
    than = json.dumps({"query": truy_van, "variables": bien or {}}).encode("utf-8")
    yc = urllib.request.Request(
        LINEAR_URL, data=than,
        headers={"Content-Type": "application/json", "Authorization": khoa},
    )
    with urllib.request.urlopen(yc, timeout=60) as r:
        d = json.loads(r.read().decode("utf-8"))
    if d.get("errors"):
        sys.exit("Linear bao loi: " + json.dumps(d["errors"], ensure_ascii=False)[:400])
    return d["data"]


# ─────────── tim chu ky dang chay
# Tu 17/08/2026 sprint tuan = CHU KY (cycle) cua Linear, khong con la du an
# "Sprint MM/DD-MM/DD/YYYY" be tu Asana sang. Linear tu sinh chu ky moi tuan.
def tim_sprint(hom_nay):
    d = linear(
        "query($t:String!){team(id:$t){activeCycle{id number startsAt endsAt}}}",
        {"t": MA_NHOM},
    )
    ck = (d.get("team") or {}).get("activeCycle")
    if not ck:
        return None
    return {"id": ck["id"], "name": f"Chu ky {ck['number']}"}


# ─────────── lay viec + binh luan trong MOT luot
TRUY_VAN_VIEC = """
query($c:String!){
  cycle(id:$c){
    issues(first:200){
      nodes{
        identifier title priority completedAt updatedAt
        state{ name type }
        assignee{ name }
        comments(last:20){ nodes{ body createdAt } }
      }
    }
  }
}
"""


def lay_viec(ma_sprint):
    d = linear(TRUY_VAN_VIEC, {"c": ma_sprint})
    return d["cycle"]["issues"]["nodes"]


# ─────────── khuon chu
def loai_viec(ten):
    t = ten or ""
    if "App" in t or "APP" in t or "Mobile" in t:
        return "APP"
    if "Web" in t:
        return "Web"
    if "Test" in t:
        return "Test"
    return "Khác"


BANG_UU_TIEN = {
    1: ("P1", "🟥"),
    2: ("P2", "🟧"),
    3: ("P3", "🟨"),
    4: ("P4", "⬜"),
    0: ("–", "⬜"),
}
BANG_TRANG_THAI = {
    "In Progress": "🕐",
    "In Review": "👀",
    "Done": "✅",
    "Todo": "⬜",
}

MAU_PHAN_TRAM = re.compile(r"(\d{1,3})\s*%")


def tom_tat(chu):
    """Duong LUI khi AI khong goi duoc: in nguyen van binh luan moi nhat.

    Lich su: ham nay tung cat cung o chu thu 15 — con so do Claude tu dat,
    Thanh khong he chot — nen cau cua Phu bi dut giua chung. Bo han.
    Tu 15/08 duong chinh la AI doc CA CHUOI binh luan roi tom (xem ai_tom).
    Ham nay chi con chay khi AI hong, de bao cao khong bao gio trong.
    """
    chu = re.sub(r"\s+", " ", (chu or "").strip())
    # Con so phan tram da in o dong tren roi, chi bo phan so nam o DAU cau
    # de khong doc thay cung mot so hai lan. Phan chu giu nguyen tung tu.
    chu = re.sub(r"^\d{1,3}\s*%[\s\-–—:.,]*", "", chu).strip()
    return chu


# ─────────── AI doc ca chuoi binh luan
# Thanh chot 15/08: moi binh luan phai duoc AI doc lai roi cho ban tom tat,
# ban tom tat THAY nguyen van. AI doc HET chuoi binh luan cua mot viec chu
# khong chi cai moi nhat. Tien do doc tu binh luan ma ra, du la chu hay so;
# doc het ma khong thay thi ghi "chua cap nhat" — TUYET DOI khong doan.
CHUA = "chưa cập nhật"

LOI_DAN = """Bạn đọc toàn bộ chuỗi bình luận của một công việc rồi báo lại cho người quản lý.

Luật bắt buộc:
- Đọc HẾT các bình luận theo thứ tự cũ đến mới, nhìn chung cả mạch, không chỉ nhìn bình luận cuối.
- Tiến độ phải đọc ra từ bình luận, dù người viết ghi bằng số hay bằng chữ. Đọc hết mà vẫn không thấy dấu hiệu nào về tiến độ thì ghi đúng hai chữ: chưa cập nhật. Tuyệt đối không tự đoán, không tự suy ra con số.
- Phần "van_de" chỉ ghi VƯỚNG MẮC, thứ đang chờ, hoặc rủi ro mà bình luận có nêu rõ. Viết tiếng Việt, một câu, tối đa hai mươi lăm chữ.
- Bình luận không nêu vướng mắc gì thì "van_de" để chuỗi rỗng. Không có gì để nói thì không nói.
- Cấm mô tả lại tiến độ bằng lời, ví dụ "đang gần xong", "mới bắt đầu", "đã hoàn thành". Con số đã in sẵn ở dòng trên.
- Cấm nhắc lại con số phần trăm. Cấm khen, cấm nhận xét chung chung.
- Không thêm thông tin không có trong bình luận.

Trả lời đúng một khối JSON, không kèm chữ nào khác:
{"tien_do": "...", "van_de": "..."}"""


def ai_tom(ten_viec, trang_thai, danh_sach_bl):
    """Goi mo hinh doc ca chuoi binh luan. Tra (tien_do, tom_tat) hoac None."""
    cua = CAU_HINH.get("MODEL_URL", "").strip()
    khoa = CAU_HINH.get("MODEL_KEY", "").strip()
    ten_mo_hinh = CAU_HINH.get("MODEL_TEN", "deepseek-chat").strip()
    if not cua or not khoa:
        return None

    dong = [f"Tên việc: {ten_viec}", f"Trạng thái trên Linear: {trang_thai}", "", "Các bình luận, cũ trước mới sau:"]
    for i, c in enumerate(danh_sach_bl, 1):
        chu = re.sub(r"\s+", " ", (c.get("body") or "").strip())
        if not chu:
            continue
        dong.append(f"{i}. {chu}")

    than = json.dumps({
        "model": ten_mo_hinh,
        "messages": [
            {"role": "system", "content": LOI_DAN},
            {"role": "user", "content": "\n".join(dong)},
        ],
        "temperature": 0,
        "max_tokens": 300,
    }).encode("utf-8")
    yc = urllib.request.Request(
        cua, data=than,
        headers={"Content-Type": "application/json", "Authorization": f"Bearer {khoa}"},
    )
    try:
        with urllib.request.urlopen(yc, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
        tra = d["choices"][0]["message"]["content"].strip()
    except Exception as e:
        print(f"  [AI hong] {ten_viec[:40]}: {e}", file=sys.stderr)
        return None

    # Mo hinh hay boc JSON trong dau ba nhay, go ra truoc khi doc.
    tra = re.sub(r"^```(?:json)?|```$", "", tra.strip()).strip()
    try:
        o = json.loads(tra)
    except Exception:
        m = re.search(r"\{.*\}", tra, re.S)
        if not m:
            print(f"  [AI tra sai khuon] {ten_viec[:40]}", file=sys.stderr)
            return None
        try:
            o = json.loads(m.group(0))
        except Exception:
            print(f"  [AI tra sai khuon] {ten_viec[:40]}", file=sys.stderr)
            return None

    tien_do = re.sub(r"\s+", " ", str(o.get("tien_do") or "").strip())
    van_de = re.sub(r"\s+", " ", str(o.get("van_de") or "").strip())
    if not tien_do or tien_do.lower() in ("null", "none", "khong ro", "không rõ", "n/a"):
        tien_do = CHUA
    # Mo hinh khi thi tra "90%", khi thi tra "90" tran. Dong dau lai mot kieu,
    # neu khong dong ghi chenh lech se doc ra "90 → 90%" trong khi khong doi gi.
    elif re.fullmatch(r"\d{1,3}", tien_do):
        tien_do = f"{tien_do}%"
    if van_de.lower() in ("null", "none", "không", "khong", "n/a", "không có"):
        van_de = ""
    return tien_do, van_de


def ap_ai(danh_sach):
    """Chay AI cho tung viec sap in. AI hong thi giu nguyen duong lui."""
    for v in danh_sach:
        if not v.get("bl_tho"):
            continue
        ra = ai_tom(v["ten"], v["trang_thai"], v["bl_tho"])
        if not ra:
            continue
        tien_do, van_de = ra
        # Viec da Done thi tien do luon la 100%, khong de AI ha xuong.
        if not v["xong"]:
            v["phan_tram"] = tien_do
        v["van_de"] = van_de


def chuan_hoa(v):
    """Doi mot viec Linear thanh cac o can de in."""
    ten_tt = (v.get("state") or {}).get("name") or ""
    loai_tt = (v.get("state") or {}).get("type") or ""
    xong = loai_tt == "completed"
    bl = (v.get("comments") or {}).get("nodes") or []
    # Xep cu truoc moi sau de AI doc dung mach cau chuyen.
    bl = sorted(bl, key=lambda c: c.get("createdAt") or "")
    bl_moi = bl[-1] if bl else None

    if xong:
        phan_tram = "100%"
        cap_nhat = tom_tat(bl_moi["body"]) if bl_moi else "đã hoàn thành"
    elif bl_moi:
        m = MAU_PHAN_TRAM.search(bl_moi.get("body") or "")
        phan_tram = f"{m.group(1)}%" if m else CHUA
        cap_nhat = tom_tat(bl_moi["body"]) or CHUA
    else:
        phan_tram = CHUA
        cap_nhat = "chưa có bình luận từ dev"

    # Thanh chot 14/08: chi dem BINH LUAN, khong dem moc sua cua Linear.
    # Moc sua bi cu keo hang loat 16:13 ngay 14/08 dong dau len 28 viec mot
    # luc, nen no khong noi len duoc ai that su co lam gi.
    moc_bl = None
    if bl_moi:
        try:
            moc_bl = datetime.fromisoformat(
                bl_moi["createdAt"].replace("Z", "+00:00")
            ).astimezone(GIO_VN)
        except Exception:
            moc_bl = None

    nhan_ut, o_mau = BANG_UU_TIEN.get(int(v.get("priority") or 0), ("–", "⬜"))
    return {
        "moc_bl": moc_bl,
        "bl_tho": bl,  # ca chuoi binh luan, de AI doc lai o buoc ap_ai
        "ma": v["identifier"],
        "ten": (v.get("title") or "").strip(),
        "loai": loai_viec(v.get("title")),
        "nhan_ut": nhan_ut,
        "o_mau": o_mau,
        "uu_tien": int(v.get("priority") or 0) or 99,
        "trang_thai": ten_tt,
        "icon_tt": BANG_TRANG_THAI.get(ten_tt, "🕐"),
        "xong": xong,
        "phan_tram": phan_tram,
        "cap_nhat": cap_nhat,
        "nguoi": ((v.get("assignee") or {}).get("name") or "Chưa gán").strip(),
        "van_de": "",
    }


# ─────────── moc tien do lan truoc (ma tu do, khong de AI doan)
# Thanh chot 19/08 theo gop y cua sep: dong ghi chu khong giai thich lai con
# so nua. Cai can la CHENH LECH so voi lan cap nhat truoc, va VUONG MAC neu co.
# Moi luot gui that, ma ghi phan tram tung viec vao tep duoi day; luot sau
# doc len de so. Chay --thu KHONG ghi de khong lam lech moc that.
TEP_MOC = os.path.join(NHA, "moc_tien_do.json")


def doc_moc():
    try:
        with open(TEP_MOC, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def ghi_moc(danh_sach, bay_gio):
    cu = doc_moc()
    moi = dict(cu)
    dau = bay_gio.strftime("%d/%m %H:%M")
    for v in danh_sach:
        o = cu.get(v["ma"]) or {}
        # Con so van y nguyen thi giu nguyen moc "dung yen tu bao gio".
        tu = o.get("tu") if o.get("phan_tram") == v["phan_tram"] else dau
        moi[v["ma"]] = {"phan_tram": v["phan_tram"], "luc": dau, "tu": tu or dau}
    try:
        with open(TEP_MOC, "w", encoding="utf-8") as f:
            json.dump(moi, f, ensure_ascii=False, indent=1)
    except Exception as e:
        print(f"  [khong ghi duoc moc] {e}", file=sys.stderr)


def dong_chenh_lech(v, moc, gon=False):
    """Mot dong so sanh voi lan truoc. Khong co gi de noi thi tra None.

    Thanh chot 19/08: ban CUOI NGAY ghi gon, bo moc ngay gio, vi no chi so
    voi luot sang cung ngay. Ban SANG giu moc, vi no so nguoc sang luot
    chieu hom truoc, khong ghi ra thi khong biet moc nam o ngay nao.
    """
    o = moc.get(v["ma"])
    if not o:
        return None
    truoc = o.get("phan_tram") or ""
    if not truoc:
        return None
    if truoc != v["phan_tram"]:
        if gon:
            return f"{truoc} → {v['phan_tram']}"
        return f"{truoc} → {v['phan_tram']} (lần trước {o.get('luc', '')})"
    # Dung yen: chi noi khi da qua it nhat mot luot truoc do.
    tu = o.get("tu") or o.get("luc") or ""
    if tu and tu != o.get("luc"):
        if gon:
            return f"{v['phan_tram']} (không có thay đổi)"
        return f"vẫn {v['phan_tram']} từ {tu}"
    return None


def in_nhom(ds, bay_gio=None, moc=None, gon=False, ghi_chu=True):
    """In mot nhom lon: gom theo nguoi, 'Chua gan' de cuoi."""
    if not ds:
        return ["(không có)"]
    theo_nguoi = {}
    for v in ds:
        theo_nguoi.setdefault(v["nguoi"], []).append(v)
    ten_nguoi = sorted(theo_nguoi, key=lambda n: (n == "Chưa gán", n))
    khoi = []
    for n in ten_nguoi:
        # Trong mot nguoi: viec xong xep truoc, roi den viec uu tien cao.
        viec = sorted(theo_nguoi[n], key=lambda v: (not v["xong"], v["uu_tien"]))
        dong = [f"👤 <b>{n}</b>"]
        nhieu = len(viec) > 1
        for v in viec:
            dau = "- " if nhieu else ""
            # Thanh chot 14/08: ten viec da tu mang nhan trong ngoac vuong
            # thi khong gan them nhan may tu doan nua, doc len bi lap.
            if v["ten"].lstrip().startswith("["):
                dong.append(f"{dau}<b>{v['ten']}</b>")
            else:
                dong.append(f"{dau}<b>[{v['loai']}]</b> <b>{v['ten']}</b>")
            # Thanh chot 19/08: chenh lech so voi lan truoc nam NGAY TREN
            # dong trang thai, thay cho con so tran. Duoi do chi con dong
            # vuong mac, va chi in khi binh luan that su co neu.
            so = v["phan_tram"]
            if ghi_chu:
                ch = dong_chenh_lech(v, moc or {}, gon)
                if ch:
                    so = ch
            # Thanh chot 14/08: o vuong mau ra TRUOC, nhan P ra SAU.
            if v["xong"]:
                dong.append(f"  {v['o_mau']} <b>{v['nhan_ut']}</b> • ✅ Done • {so}")
            else:
                dong.append(
                    f"  {v['o_mau']} <b>{v['nhan_ut']}</b> • "
                    f"{v['icon_tt']} {v['trang_thai']} • {so}"
                )
            if ghi_chu and (v.get("van_de") or "").strip():
                dong.append(f"  ❗ {v['van_de'].strip()}")
            # Thanh chot 14/08: co nguoi lam that ma viec van nam Backlog.
            if v.get("nhac_keo"):
                dong.append(
                    "  ⚠️ Việc này vẫn ở Backlog, cần chuyển sang In Progress"
                )
        khoi.append("\n".join(dong))
    return ["\n\n".join(khoi)]


def dung_chu(kieu, bay_gio, viec, moc=None):
    ngay = bay_gio.strftime("%d/%m/%Y")
    gio = bay_gio.strftime("%H:%M")
    hom_nay = bay_gio.date()

    # Thanh chot 14/08: doc CA BACKLOG. Viec nam Backlog ma co binh luan
    # trong vong 7 ngay la dau hieu co nguoi dang lam that, chi la quen keo
    # sang In Progress. Van dua vao bao cao, kem loi nhac keo trang thai.
    dang_lam = []
    for v in viec:
        loai_tt = (v.get("state") or {}).get("type") or ""
        if loai_tt == "started":
            dang_lam.append(chuan_hoa(v))
        elif loai_tt in ("backlog", "unstarted"):
            o = chuan_hoa(v)
            if o["moc_bl"] and (bay_gio - o["moc_bl"]) <= timedelta(days=7):
                # Chi nhac keo trang thai khi viec that su con nam Backlog.
                # Viec da o Todo la da chot lam tuan nay, khong nhac nua.
                o["nhac_keo"] = loai_tt == "backlog"
                dang_lam.append(o)

    if kieu == "sang":
        tieu_de = f"📋 BÁO CÁO CÔNG VIỆC SÁNG {ngay} ({gio})"
        if not dang_lam:
            return tieu_de + "\n\nKhông có việc nào đang làm dở.", []
        ap_ai(dang_lam)
        # Thanh chot 19/08: ban DAU NGAY khong in them dong ghi chu nao,
        # chi ten viec, trang thai va phan tram.
        return tieu_de + "\n\n" + "\n\n".join(
            in_nhom(dang_lam, bay_gio, ghi_chu=False)
        ), dang_lam

    # ── Cuoi ngay tra loi dung mot cau hoi: HOM NAY CO GI CHUYEN DONG.
    # Thanh chot 14/08, ba phan theo dung thu tu duoi day.

    # Phan 1: viec co MOC HOAN THANH nam trong ngay hom nay.
    # Khong lay trong vong 24 tieng nua — viec xong hom qua se hien them
    # mot luot nua vao chieu nay, doc len tuong hom nay lam duoc nhieu hon that.
    xong_hom_nay = []
    for v in viec:
        if (v.get("state") or {}).get("type") != "completed":
            continue
        moc_xong = v.get("completedAt") or ""
        try:
            t = datetime.fromisoformat(moc_xong.replace("Z", "+00:00")).astimezone(GIO_VN)
        except Exception:
            continue
        if t.date() == hom_nay:
            xong_hom_nay.append(chuan_hoa(v))

    # Phan 2: viec co binh luan moi trong hom nay.
    # Thanh chot 14/08: BO han muc "dang lam nhung im lang".
    co_bao = [v for v in dang_lam if v["moc_bl"] and v["moc_bl"].date() == hom_nay]

    tieu_de = f"📋 BÁO CÁO CÔNG VIỆC CUỐI NGÀY {ngay} ({gio})"
    if not xong_hom_nay and not co_bao:
        return tieu_de + "\n\nHôm nay không có việc nào hoàn thành hay có báo tiến độ.", []

    # Thanh chot 15/08: GOM THEO NGUOI, khong tach muc theo trang thai nua.
    # Mot nguoi doc lien mot khoi, viec xong xep truoc viec dang lam. Trang
    # thai van doc duoc ngay tren tung dong viec.
    gop, da_co = [], set()
    for v in xong_hom_nay + co_bao:
        if v["ma"] in da_co:
            continue
        da_co.add(v["ma"])
        gop.append(v)

    # Chi cho AI doc dung nhung viec sap in ra, khoi ton luot goi.
    ap_ai(gop)

    return tieu_de + "\n\n" + "\n\n".join(in_nhom(gop, bay_gio, moc, gon=True)), gop


# ─────────── gui
def gui(chu):
    cua = CAU_HINH.get("WEBHOOK", "")
    if not cua:
        sys.exit("Thieu WEBHOOK trong .env")
    than = json.dumps({"title": "", "message": chu}).encode("utf-8")
    yc = urllib.request.Request(cua, data=than, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(yc, timeout=60) as r:
        return r.status


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--sang", action="store_true")
    p.add_argument("--cuoi-ngay", dest="cuoi_ngay", action="store_true")
    p.add_argument("--thu", action="store_true", help="in ra man hinh, khong gui")
    a = p.parse_args()
    if not (a.sang or a.cuoi_ngay):
        p.error("chon --sang hoac --cuoi-ngay")

    bay_gio = datetime.now(GIO_VN)
    sprint = tim_sprint(bay_gio.date())
    if not sprint:
        chu = (
            f"📋 BÁO CÁO CÔNG VIỆC {'SÁNG' if a.sang else 'CUỐI NGÀY'} "
            f"{bay_gio.strftime('%d/%m/%Y')} ({bay_gio.strftime('%H:%M')})"
            "\n\nKhông tìm thấy đợt sprint nào trên Linear."
        )
        da_in = []
    else:
        viec = lay_viec(sprint["id"])
        moc = doc_moc()
        chu, da_in = dung_chu("sang" if a.sang else "cuoi", bay_gio, viec, moc)

    if a.thu:
        print(chu)
        return
    ma = gui(chu)
    # Chi luot gui THAT moi doi moc, de chay thu bao nhieu lan cung khong lech.
    ghi_moc(da_in, bay_gio)
    print(f"[{bay_gio:%Y-%m-%d %H:%M:%S}] da gui, ma {ma}, {len(chu)} ky tu")


if __name__ == "__main__":
    main()
