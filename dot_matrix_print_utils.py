import os
import logging
from textwrap import wrap
from PIL import Image, ImageDraw, ImageFont, ImageWin
import win32print
import win32con
import win32ui
logger = logging.getLogger(__name__)

def print_epd_card_dot_matrix(patient_data, width=80):
    def center(text, width=width):
        return text.center(width)

    def safe(key):
        val = patient_data.get(key)
        return "" if val is None or str(val).strip().lower() in ("", "none", "null", "n/a") else str(val)

    def safe_date(key):
        val = patient_data.get(key)
        try:
            import datetime
            if isinstance(val, datetime.date):
                return val.strftime("%d/%m/%Y")
            elif isinstance(val, str) and len(val) >= 10:
                from datetime import datetime as dt
                try:
                    if "/" in val:
                        return val
                    elif "-" in val:
                        return dt.strptime(val[:10], "%Y-%m-%d").strftime("%d/%m/%Y")
                except Exception:
                    return val
            return "" if not val else str(val)
        except Exception:
            return "" if not val else str(val)

    # Define positions
    left_label_pos = 0
    left_value_pos = 20
    right_label_pos = 44
    right_value_pos = 60
    field_width = right_label_pos - left_value_pos - 1
    right_field_width = width - right_value_pos

    left_labels = [
        ("Reg. No.:", safe('registration_number')),
        ("Name:", (safe('first_name') + " " + safe('last_name')).strip()),
        ("Father's/Husband's Name:", safe('father_name')),
        ("Address:", safe('address')),
        ("Town:", safe('town')),
        ("Date:", safe_date('date')),
    ]
    right_labels = [
        ("Age:", safe('age')),
        ("Gender:", safe('gender')),
        ("Mobile:", safe('mobile_number')),
        ("Department:", safe('medical_department')),
        ("State:", safe('state')),
        ("Attending Doctor:", safe('attending_doctor')),
    ]

    lines = []
    lines.append(center("SRI RAM JANKI MEDICAL COLLEGE & HOSPITAL"))
    lines.append(center("MUZAFFARPUR"))
    lines.append(center("EPD PATIENT CARD"))
    lines.append("")

    for i in range(6):
        # Wrap values if too long
        left_value_lines = wrap(left_labels[i][1], field_width) or [""]
        right_value_lines = wrap(right_labels[i][1], right_field_width) or [""]
        max_lines = max(len(left_value_lines), len(right_value_lines))
        for j in range(max_lines):
            line = ""
            # Left label and value
            if j == 0:
                left_label = left_labels[i][0]
            else:
                left_label = ""
            left_value = left_value_lines[j] if j < len(left_value_lines) else ""
            right_label = right_labels[i][0] if j == 0 else ""
            right_value = right_value_lines[j] if j < len(right_value_lines) else ""
            # Place at fixed positions
            line += " " * (left_label_pos - len(line)) + left_label
            line += " " * (left_value_pos - len(line)) + left_value
            line += " " * (right_label_pos - len(line)) + right_label
            line += " " * (right_value_pos - len(line)) + right_value
            lines.append(line)

    lines.append("")
    # Table header
    date_w = 13
    notes_w = 36
    advice_w = 17
    table_line = "+" + "-"*date_w + "+" + "-"*notes_w + "+" + "-"*advice_w + "+"
    table_hdr  = f"| {'Date/Time':^{date_w}} | {'Clinical Notes':^{notes_w}} | {'Advice':^{advice_w}} |"
    lines.append(table_line)
    lines.append(table_hdr)
    lines.append(table_line)
    for _ in range(7):
        lines.append(f"| {'':<{date_w}} | {'':<{notes_w}} | {'':<{advice_w}} |")
    lines.append(table_line)
    lines.append("")

    output = "\n".join(lines)
    print(output)
    return output

def print_text_to_printer(file_path, printer_name=None):
    # Read the text file content
    with open(file_path, "r", encoding="utf-8") as f:
        text = f.read()

    # Use specified printer or default
    if not printer_name or printer_name.lower() == "default":
        printer_name = win32print.GetDefaultPrinter()

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)
        hdc.StartDoc(file_path)
        hdc.StartPage()

        # Set font (you can adjust height/spacing as needed)
        font = win32ui.CreateFont({'name': 'Consolas', 'height': 20})
        hdc.SelectObject(font)

        y = 100
        for line in text.splitlines():
            hdc.TextOut(100, y, line)
            y += 30  # Adjust spacing as needed

        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
    finally:
        win32print.ClosePrinter(hprinter)

def _register_private_font(font_path):
    """
    Register a TTF for this process only using AddFontResourceExW via ctypes.
    Returns True if AddFontResourceExW reported a non-zero add count.
    """
    if os.name != "nt":
        return False
    try:
        import ctypes
        import ctypes.wintypes as wintypes
    except Exception as e:
        logger.debug("ctypes import failed for font registration: %s", e)
        return False

    if not os.path.isfile(font_path):
        logger.debug("Font path not found: %s", font_path)
        return False

    try:
        FR_PRIVATE = 0x10
        # AddFontResourceExW returns number of fonts added (non-zero on success)
        added = ctypes.windll.gdi32.AddFontResourceExW(ctypes.c_wchar_p(font_path), ctypes.c_uint(FR_PRIVATE), ctypes.c_void_p(0))
        if added:
            logger.info("Registered private font (ctypes.AddFontResourceExW): %s (added=%s)", font_path, added)
            return True
        else:
            logger.warning("AddFontResourceExW returned 0 for %s", font_path)
            return False
    except Exception as e:
        logger.exception("Failed to register private font via ctypes: %s", e)
        return False


def _render_text_with_windows_gdi(text, face_name, font_size_px, text_color=(0, 0, 0), max_width=None):
    """
    Render `text` using Windows GDI (DrawText) to a PIL RGBA image with transparent background.
    face_name must be a font family name available to GDI (e.g., "Mangal" or the family returned by PIL).
    font_size_px is approximate pixel height for the font.
    max_width: optional maximum width in pixels for word-wrap.
    Returns PIL.Image (RGBA).
    """
    if os.name != "nt":
        raise RuntimeError("GDI renderer only available on Windows")

    try:
        import win32ui, win32gui, win32con, win32api
    except Exception as e:
        raise RuntimeError("pywin32 is required for Windows GDI rendering") from e

    # Estimate bitmap size
    bmp_w = max(800, int(max_width) if max_width else 1200)
    bmp_h = max(64, int(font_size_px * 3))

    # Create screen and memory DCs
    hdc_screen = win32gui.GetDC(0)
    dc_screen = win32ui.CreateDCFromHandle(hdc_screen)
    mem_dc = dc_screen.CreateCompatibleDC()

    bmp = win32ui.CreateBitmap()
    bmp.CreateCompatibleBitmap(dc_screen, bmp_w, bmp_h)
    old_bmp = mem_dc.SelectObject(bmp)

    # Build minimal font spec dictionary for win32ui.CreateFont (supported keys only)
    font_spec = {
        "name": face_name,
        "height": -int(font_size_px),     # negative = character height in pixels
        "weight": win32con.FW_NORMAL,
        "italic": False,
        "underline": False,
        "charset": win32con.DEFAULT_CHARSET,
    }

    gdi_font = None
    img = None
    try:
        # Create and select font
        gdi_font = win32ui.CreateFont(font_spec)
        old_font = mem_dc.SelectObject(gdi_font)

        # Transparent background and text color
        mem_dc.SetBkMode(win32con.TRANSPARENT)
        mem_dc.SetTextColor(win32api.RGB(*text_color))

        # DrawText supports shaping via Uniscribe
        rect = (4, 4, bmp_w - 4, bmp_h - 4)
        flags = win32con.DT_LEFT | win32con.DT_NOPREFIX | win32con.DT_WORDBREAK
        try:
            mem_dc.DrawText(text, rect, flags)
        except Exception:
            mem_dc.TextOut(4, 4, text)

        # Extract bitmap and convert to PIL image
        bmp_info = bmp.GetInfo()
        bmp_bits = bmp.GetBitmapBits(True)
        img = Image.frombuffer('RGB', (bmp_info['bmWidth'], bmp_info['bmHeight']), bmp_bits, 'raw', 'BGRX', 0, 1)
        img = img.transpose(Image.FLIP_TOP_BOTTOM)
        img = img.convert("RGBA")

        # Make near-white pixels transparent
        datas = img.getdata()
        new_data = []
        for r, g, b, a in datas:
            if r > 250 and g > 250 and b > 250:
                new_data.append((255, 255, 255, 0))
            else:
                new_data.append((r, g, b, 255))
        img.putdata(new_data)

    except Exception as e:
        # Let caller fallback to PIL; include the exception in the log
        logger.exception("GDI render/create font failed: %s", e)
        raise

    finally:
        # Cleanup GDI objects and DCs (use handles so we don't rely on pywin32 DeleteObject methods)
        try:
            if 'old_font' in locals():
                try:
                    mem_dc.SelectObject(old_font)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            if 'old_bmp' in locals():
                try:
                    mem_dc.SelectObject(old_bmp)
                except Exception:
                    pass
        except Exception:
            pass

        # Delete bitmap via its handle (PyCBitmap may not expose DeleteObject)
        try:
            try:
                bmp_handle = bmp.GetHandle()
                win32gui.DeleteObject(bmp_handle)
            except Exception:
                # fallback: try bmp.DeleteObject if present
                try:
                    bmp.DeleteObject()
                except Exception:
                    pass
        except Exception:
            pass

        # Delete font object if possible
        try:
            if gdi_font is not None:
                try:
                    # prefer wrapper DeleteObject if available
                    if hasattr(gdi_font, "DeleteObject"):
                        gdi_font.DeleteObject()
                    else:
                        # try to get raw handle and delete
                        if hasattr(gdi_font, "GetHandle"):
                            hfont = gdi_font.GetHandle()
                            win32gui.DeleteObject(hfont)
                except Exception:
                    pass
        except Exception:
            pass

        try:
            mem_dc.DeleteDC()
        except Exception:
            pass

        try:
            win32gui.ReleaseDC(0, hdc_screen)
        except Exception:
            pass

    # Trim transparent margin
    if img is not None:
        bbox = img.getbbox()
        if bbox:
            img = img.crop(bbox)

    return img

def generate_opd_card_image(patient_data, a4_dpi=150):
    """
    A4 OPD card generator that uses:
     - Windows: GDI rendering for Hindi text using a bundled Mangal.ttf (registered privately at runtime).
     - Non-Windows: Pillow truetype drawing (existing behavior).
    Place Mangal.ttf in a 'fonts' folder next to this module or set OPD_HINDI_FONT_PATH env var.
    """
    width, height = int(8.27 * a4_dpi), int(11.69 * a4_dpi)
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    # locate bundled font (priority: env var OPD_HINDI_FONT_PATH, then fonts/Mangal.ttf relative to module)
    env_fp = os.environ.get("OPD_HINDI_FONT_PATH")
    module_dir = os.path.dirname(__file__)
    bundled_fp = os.path.join(module_dir, "fonts", "Mangal.ttf")
    font_path = env_fp if env_fp and os.path.isfile(env_fp) else (bundled_fp if os.path.isfile(bundled_fp) else None)

    # Normal/header fonts (Pillow) - fallbacks
    try:
        header_font = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arialbd.ttf"), 32)
    except Exception:
        try:
            header_font = ImageFont.truetype("arialbd.ttf", 32)
        except Exception:
            header_font = ImageFont.load_default()
    try:
        normal_font = ImageFont.truetype(os.path.join(os.environ.get("WINDIR", r"C:\Windows"), "Fonts", "arial.ttf"), 20)
    except Exception:
        normal_font = ImageFont.load_default()

    # If on Windows and we have a font file, register it privately so GDI can use it
    gdi_face_name = "Mangal"  # face name expected inside the TTF
    if os.name == "nt" and font_path:
        try:
            _register_private_font(font_path)
        except Exception as e:
            logger.debug("Private font registration failed: %s", e)

    # Short safe accessor for patient_data
    safe = lambda key, d="": str(patient_data.get(key, d) or d)

    y = 60

    # --- HINDI HEADER: Use GDI on Windows (for correct shaping), else PIL ---
    header_line1 = "अनुसूची • 6 धर्म संख्या • 10"
    header_line2 = "श्री राम जानकी मेडिकल कॉलेज एवं अस्पताल समस्तीपुर"
    if os.name == "nt":
        try:
            # Render using GDI and paste centered
            header_img1 = _render_text_with_windows_gdi(header_line1, gdi_face_name, font_size_px=28, text_color=(0, 0, 0), max_width=int(width*0.9))
            image.paste(header_img1, ((width - header_img1.width) // 2, y), header_img1)
            y += header_img1.height + 6
            header_img2 = _render_text_with_windows_gdi(header_line2, gdi_face_name, font_size_px=24, text_color=(0, 0, 0), max_width=int(width*0.9))
            image.paste(header_img2, ((width - header_img2.width) // 2, y), header_img2)
            y += header_img2.height + 10
            # English "(OPD PATIENT CARD)"
            draw.text((width // 2, y), "(OPD PATIENT CARD)", fill="black", anchor="ma", font=header_font)
            y += 35
        except Exception as e:
            logger.exception("GDI header rendering failed, falling back to PIL: %s", e)
            draw.text((width // 2, y), header_line1, fill="black", anchor="ma", font=normal_font)
            y += 28
            draw.text((width // 2, y), header_line2, fill="black", anchor="ma", font=normal_font)
            y += 28
            draw.text((width // 2, y), "(OPD PATIENT CARD)", fill="black", anchor="ma", font=header_font)
            y += 35
    else:
        draw.text((width // 2, y), header_line1, fill="black", anchor="ma", font=normal_font)
        y += 28
        draw.text((width // 2, y), header_line2, fill="black", anchor="ma", font=normal_font)
        y += 28
        draw.text((width // 2, y), "(OPD PATIENT CARD)", fill="black", anchor="ma", font=header_font)
        y += 35

    draw.line([(90, y), (width - 90, y)], fill="black", width=2)
    y += 15

    # Registration details (unchanged)
    draw.text((100, y), f"Registration No.: {safe('registration_number')}", fill="black", font=normal_font)
    draw.text((width // 2, y), f"Abha No.: {safe('abha_number')}", fill="black", font=normal_font, anchor="ma")
    draw.text((width - 200, y), f"Date: {safe('registration_date')}", fill="black", font=normal_font)
    y += 25

    # Patient Name and Age
    draw.text((100, y), f"Patient Name: {safe('first_name')} {safe('last_name')}", fill="black", font=normal_font)
    draw.text((width - 200, y), f"Age: {safe('age')} M/Yrs", fill="black", font=normal_font)
    y += 25

    # Father's/Guardian/Husband Name
    father = safe('father_name')
    draw.text((100, y), f"Father's/Guardian/Husband Name: {father}", fill="black", font=normal_font)
    y += 25

    # Gender
    draw.text((100, y), f"Gender: {safe('gender')}", fill="black", font=normal_font)
    y += 25

    # Address
    address_value = f"{safe('address')} {safe('town')} {safe('state')}"
    draw.text((100, y), f"Address: {address_value}", fill="black", font=normal_font)
    y += 25

    # Mobile and Fee: draw Hindi fee via GDI if on Windows
    draw.text((100, y), f"Mobile No: {safe('mobile_number')}", fill="black", font=normal_font)
    fee_text = f"निबंधन शुल्क: ₹ {safe('registration_fee', '5.00')}"
    if os.name == "nt":
        try:
            fee_img = _render_text_with_windows_gdi(fee_text, gdi_face_name, font_size_px=20, text_color=(0,0,0))
            image.paste(fee_img, (width - 250, y - 2), fee_img)
        except Exception:
            draw.text((width - 250, y), fee_text, fill="black", font=normal_font)
    else:
        draw.text((width - 250, y), fee_text, fill="black", font=normal_font)
    y += 25

    # Divider
    draw.line([(90, y), (width - 90, y)], fill="black", width=2)
    y += 15

    # Examination fields
    fields = ["Weight :", "BP :", "PR :", "Room No. :"]
    for i, lbl in enumerate(fields):
        draw.text((100, y + i * 22), lbl, fill="black", font=normal_font)

    y += len(fields) * 22 + 10
    draw.line([(90, y), (width - 90, y)], fill="black", width=2)
    y += 20

    # Footer Hindi note: use GDI on Windows
    note_text = "नोट• कृपया इस टिकट को हमेशा साथ लावें अन्यथा दवा नहीं मिलेगी ।"
    if os.name == "nt":
        try:
            note_img = _render_text_with_windows_gdi(note_text, gdi_face_name, font_size_px=20, text_color=(0,0,0), max_width=width - 180)
            note_y = height - note_img.height - 40
            image.paste(note_img, (100, note_y), note_img)
        except Exception:
            bbox = ImageFont.load_default().getbbox(note_text)
            note_height = bbox[3] - bbox[1] if bbox else 16
            note_y = height - note_height - 40
            draw.text((100, note_y), note_text, fill="black", font=normal_font)
    else:
        bbox = normal_font.getbbox(note_text) if hasattr(normal_font, "getbbox") else None
        note_height = (bbox[3] - bbox[1]) if bbox else 16
        note_y = height - note_height - 40
        draw.text((100, note_y), note_text, fill="black", font=normal_font)

    return image


def print_image_to_printer(image, printer_name=None):
    if not printer_name or printer_name.lower() == "default":
        printer_name = win32print.GetDefaultPrinter()

    hprinter = win32print.OpenPrinter(printer_name)
    try:
        hdc = win32ui.CreateDC()
        hdc.CreatePrinterDC(printer_name)

        # --- THIS IS THE KEY: get the real printable area at printer DPI ---
        phys_width = hdc.GetDeviceCaps(win32con.PHYSICALWIDTH)
        phys_height = hdc.GetDeviceCaps(win32con.PHYSICALHEIGHT)
        printable_x = hdc.GetDeviceCaps(win32con.PHYSICALOFFSETX)
        printable_y = hdc.GetDeviceCaps(win32con.PHYSICALOFFSETY)
        printable_width = hdc.GetDeviceCaps(win32con.HORZRES)
        printable_height = hdc.GetDeviceCaps(win32con.VERTRES)

        hdc.StartDoc("OPD Patient Card")
        hdc.StartPage()
        dib = ImageWin.Dib(image)
        # Draw to the full printable area!
        dib.draw(
            hdc.GetHandleOutput(),
            (printable_x, printable_y, printable_x + printable_width, printable_y + printable_height)
        )
        hdc.EndPage()
        hdc.EndDoc()
        hdc.DeleteDC()
    finally:
        win32print.ClosePrinter(hprinter)

def print_opd_card_a4_fast(patient_data, printer_name="default"):
    image = generate_opd_card_image(patient_data, a4_dpi=150)  # Fast/low DPI
    print_image_to_printer(image, printer_name)

def draw_dotted_line(draw, x1, y, x2, dot_length=10, gap_length=7):
    x = x1
    while x < x2:
        draw.line([(x, y), (min(x + dot_length, x2), y)], fill="black", width=1)
        x += dot_length + gap_length

def truncate_text(text, max_chars):
    # Truncate text to avoid overflow, add ellipsis if needed
    return text if len(text) <= max_chars else text[:max_chars-3] + "..."

def generate_ipd_bed_head_ticket_image(patient_data, dpi=150):
    from PIL import Image, ImageDraw, ImageFont

    width, height = int(8.27 * dpi), int(11.69 * dpi)  # A4
    image = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(image)

    # Fonts
    header_font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 38)
    bold_font = ImageFont.truetype("C:\\Windows\\Fonts\\arialbd.ttf", 22)
    normal_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 20)
    small_font = ImageFont.truetype("C:\\Windows\\Fonts\\arial.ttf", 16)

    margin_left = 70
    margin_right = 70
    margin_top = 80
    margin_bottom = 80

    draw.rectangle([margin_left, margin_top, width - margin_right, height - margin_bottom], outline="black", width=2)

    y = margin_top + 40
    center_x = width // 2
    draw.text((center_x, y), "SRI RAM JANKI MEDICAL COLLEGE & HOSPITAL", font=header_font, fill="black", anchor="ma")
    y += 50
    draw.text((center_x, y), "SAMASTIPUR", font=header_font, fill="black", anchor="ma")
    y += 50
    bedhead_text = "BED HEAD TICKET"
    draw.text((center_x, y), bedhead_text, font=bold_font, fill="black", anchor="ma")
    bbox = draw.textbbox((center_x, y), bedhead_text, font=bold_font, anchor="ma")
    underline_y = bbox[3] + 4
    draw.line((bbox[0], underline_y, bbox[2], underline_y), fill="black", width=2)
    y = underline_y + 16

    safe = lambda k, d="": str(patient_data.get(k, d) or d)

    # Variable dotted line lengths for each field
    dotted_lengths = {
        "ward": 250,
        "side": 200,
        "year": 100,
        "registration_number": 200,
        "bed_number": 150,
        "name": 240,
        "age": 80,
        "sex": 80,
        "religion": 140,
        "father_name": 350,
        "mother_name": 350,
        "village": 250,
        "po": 180,
        "ps": 220,
        "distt": 220,
        "admission_date": 200,
        "discharge_date": 200,
        "result_advice": 350,
    }

    row_height = normal_font.size + 30  # Increase row height for vertical spacing

    # For dynamic, non-overlapping multi-field rows
    def multi_field_row(fields, y, font_label, font_value, max_chars=20, gap=30):
        x = margin_left + 22
        min_gap = gap
        for label, value, key in fields:
            value = truncate_text(str(value), max_chars)
            # Draw label
            draw.text((x, y), label, font=font_label, fill="black")
            label_width = draw.textlength(label, font=font_label)
            value_x = x + label_width + 8
            # Draw value
            draw.text((value_x, y), value, font=font_value, fill="black")
            value_width = draw.textlength(value, font=font_value)
            value_height = font_value.size
            dotted_y = y + value_height + 6
            dotted_len = dotted_lengths.get(key, 120)
            draw_dotted_line(draw, value_x, dotted_y, value_x + dotted_len)
            # Advance x for next field
            x = value_x + max(value_width, dotted_len) + min_gap
        return y + row_height

    # For pairs
    def draw_paired_row(label1, value1, key1, label2, value2, key2, y):
        return multi_field_row(
            [(label1, value1, key1), (label2, value2, key2)],
            y, normal_font, normal_font, max_chars=20, gap=60
        )

    # For triples
    def triple_field_row(label1, value1, key1, label2, value2, key2, label3, value3, key3, y):
        return multi_field_row(
            [(label1, value1, key1), (label2, value2, key2), (label3, value3, key3)],
            y, normal_font, normal_font, max_chars=18, gap=50
        )

    # For quads
    def quad_field_row(label1, value1, key1, label2, value2, key2, label3, value3, key3, label4, value4, key4, y):
        return multi_field_row(
            [(label1, value1, key1), (label2, value2, key2), (label3, value3, key3), (label4, value4, key4)],
            y, normal_font, normal_font, max_chars=15, gap=30
        )

    # Ward | Side
    y = draw_paired_row("Ward:", safe("ward", ""), "ward", "Side:", safe("side", ""), "side", y)
    # Year | Reg No | Bed No
    y = triple_field_row("Year:", safe("year", ""), "year",
                         "Reg. No.:", safe("registration_number", ""), "registration_number",
                         "Bed No.:", safe("bed_number", ""), "bed_number", y)
    # Name | Age | Sex | Religion
    y = quad_field_row("Name:", safe("name", safe("first_name", "") + " " + safe("last_name", "")), "name",
                       "Age:", safe("age", ""), "age",
                       "Sex:", safe("sex", safe("gender", "")), "sex",
                       "Religion:", safe("religion", ""), "religion", y)
    # Father's / Husband's Name
    y = multi_field_row([("Father's / Husband's Name:", safe("father_name", ""), "father_name")], y, normal_font, normal_font, max_chars=25, gap=0)
    # Mother's Name
    y = multi_field_row([("Mother's Name:", safe("mother_name", ""), "mother_name")], y, normal_font, normal_font, max_chars=25, gap=0)
    # Village | PO
    y = draw_paired_row("Village/Mohalla:", safe("village", safe("address", "")), "village", "P.O.:", safe("po", safe("post_office", "")), "po", y)
    # PS | Distt
    y = draw_paired_row("P.S.:", safe("ps", ""), "ps", "Distt.:", safe("distt", safe("town", "")), "distt", y)
    # Admission/Discharge Date
    y = draw_paired_row("Date & Time of Admission:", safe("admission_datetime", ""), "admission_datetime",
                        "Date & Time of Discharge:", safe("discharge_datetime", ""), "discharge_datetime", y)
    # Result & Advice
    y = multi_field_row([("Result & Advice:", safe("result_advice", safe("notes", "")), "result_advice")], y, normal_font, normal_font, max_chars=35, gap=0)

    y += 18

    # --- Diagnosis Section ---
    draw.text((margin_left + 22, y), "Diagnosis (a) Provisional", font=bold_font, fill="black")
    draw.text((margin_left + 22 + 300, y), safe("diagnosis_provisional", ""), font=normal_font, fill="black")
    y += 30
    draw.text((margin_left + 22 + 30, y), "(b) Final", font=bold_font, fill="black")
    draw.text((margin_left + 22 + 300, y), safe("diagnosis_final", ""), font=normal_font, fill="black")
    y += 30
    draw.text((margin_left + 22 + 30, y), "(c) ICD X", font=bold_font, fill="black")
    draw.text((margin_left + 22 + 300, y), safe("diagnosis_icdx", ""), font=normal_font, fill="black")
    y += 40

    # --- Clinical Notes Table ---
    x_l = margin_left + 22
    max_right = width - margin_right - 22
    table_top = y
    table_left = x_l
    table_width = max_right - x_l
    table_height = 430

    draw.rectangle([table_left, table_top, table_left + table_width, table_top + table_height], outline="black", width=2)
    draw.line([table_left, table_top + 45, table_left + table_width, table_top + 45], fill="black", width=2)
    col_date = 0
    col_notes = int(table_width * 0.24)
    col_advice = int(table_width * 0.72)
    draw.line([table_left + col_notes, table_top, table_left + col_notes, table_top + table_height], fill="black", width=2)
    draw.line([table_left + col_advice, table_top, table_left + col_advice, table_top + table_height], fill="black", width=2)
    draw.text((table_left + 16, table_top + 13), "Date", font=bold_font, fill="black")
    draw.text((table_left + col_notes + 16, table_top + 13), "Clinical Notes", font=bold_font, fill="black")
    draw.text((table_left + col_advice + 16, table_top + 13), "Advice", font=bold_font, fill="black")

    return image

def print_ipd_bed_head_ticket(patient_data, printer_name=None):
    # Always use admin-selected printer for IPD tickets
    from printer_manager import load_printer_choice
    if not printer_name or printer_name == "default":
        printer_name = load_printer_choice()
    image = generate_ipd_bed_head_ticket_image(patient_data, dpi=150)
    print_image_to_printer(image, printer_name)


def print_reporting_summary_a4(report_data, from_date, to_date, user_filter, dept_filter):
    """
    Prints a reporting summary on A4, dot-matrix fast style, with center-aligned hospital name and report title.
    report_data: list of dicts, each with keys: "Date", "User", "Department", "OPD", "IPD", "EPD", "Total"
    """
    # A4 size in pixels at 300 DPI
    DPI = 300
    A4_WIDTH_PX, A4_HEIGHT_PX = int(8.27 * DPI), int(11.69 * DPI)

    # Font settings (monospace for dot-matrix look)
    font_path = "C:\\Windows\\Fonts\\consola.ttf"  # Use Consolas, or another monospaced font present on your system
    font_size = 18
    font = ImageFont.truetype(font_path, font_size)

    # Layout settings
    left_margin = 70
    right_margin = 70
    top_margin = 70
    bottom_margin = 70
    line_height = font_size + 8

    # Column definitions
    columns = [
        ("Date", 12),
        ("User", 14),
        ("Department", 16),
        ("OPD", 5),
        ("IPD", 5),
        ("EPD", 5),
        ("Total", 6),
    ]
    col_headers = [col[0] for col in columns]
    col_widths = [col[1] for col in columns]
    table_char_width = sum(col_widths) + len(col_widths) - 1

    # Use getbbox instead of getsize for Pillow >= 10
    def get_char_width(text):
        bbox = font.getbbox(text)
        return bbox[2] - bbox[0]

    def center_text(text, width_chars):
        # Calculate pixel width of a line, then pad with spaces to center in width_chars
        text_width_px = get_char_width(text)
        total_width_px = get_char_width("W") * width_chars
        spaces_needed = max((total_width_px - text_width_px) // get_char_width(" "), 0)
        left_spaces = spaces_needed // 2
        right_spaces = spaces_needed - left_spaces
        return (" " * left_spaces) + text + (" " * right_spaces)

    # Prepare static lines
    header1 = center_text("SRI RAM JANKI MEDICAL COLLEGE & HOSPITAL MUZAFFARPUR", table_char_width)
    header2 = center_text("REPORTING SUMMARY", table_char_width)
    filter_line = f"From: {from_date}  To: {to_date}  User: {user_filter}  Dept: {dept_filter}"
    sep = "-" * table_char_width
    table_header = ""
    for i, (h, w) in enumerate(zip(col_headers, col_widths)):
        table_header += h.ljust(w)
        if i < len(col_headers) - 1:
            table_header += " "

    footer = "NOTE: Please keep this slip for your records."

    # Pagination logic
    max_lines_per_page = (A4_HEIGHT_PX - top_margin - bottom_margin) // line_height - 8  # headers/footers
    page_entries = []
    cur_page = []

    for i, row in enumerate(report_data):
        cell_values = [
            str(row.get("Date", ""))[:12],
            str(row.get("User", ""))[:14],
            str(row.get("Department", ""))[:16],
            str(row.get("OPD", ""))[:5],
            str(row.get("IPD", ""))[:5],
            str(row.get("EPD", ""))[:5],
            str(row.get("Total", ""))[:6],
        ]
        line = ""
        for j, (val, w) in enumerate(zip(cell_values, col_widths)):
            line += val.ljust(w)
            if j < len(cell_values) - 1:
                line += " "
        cur_page.append(line)
        if len(cur_page) == max_lines_per_page or i == len(report_data) - 1:
            page_entries.append(cur_page)
            cur_page = []

    # Print each page as an image to the printer
    printer_name = win32print.GetDefaultPrinter()
    hprinter = win32print.OpenPrinter(printer_name)
    hdc = win32ui.CreateDC()
    hdc.CreatePrinterDC(printer_name)
    hdc.StartDoc("Reporting Summary")

    for page_num, lines_on_page in enumerate(page_entries):
        # Create A4 image
        image = Image.new("RGB", (A4_WIDTH_PX, A4_HEIGHT_PX), "white")
        draw = ImageDraw.Draw(image)
        y = top_margin

        # Centered header
        draw.text((left_margin, y), header1, font=font, fill="black")
        y += line_height
        draw.text((left_margin, y), header2, font=font, fill="black")
        y += line_height
        draw.text((left_margin, y), filter_line, font=font, fill="black")
        y += line_height
        draw.text((left_margin, y), sep, font=font, fill="black")
        y += line_height
        draw.text((left_margin, y), table_header, font=font, fill="black")
        y += line_height
        draw.text((left_margin, y), sep, font=font, fill="black")
        y += line_height

        # Table rows
        for line in lines_on_page:
            draw.text((left_margin, y), line, font=font, fill="black")
            y += line_height

        # Footer and Page Number
        y = A4_HEIGHT_PX - bottom_margin - 2 * line_height
        draw.text((left_margin, y), sep, font=font, fill="black")
        y += line_height
        draw.text((left_margin, y), footer, font=font, fill="black")
        # Page number (right-aligned)
        page_text = f"Page {page_num + 1} of {len(page_entries)}"
        page_text_width = get_char_width(page_text)
        draw.text(
            (A4_WIDTH_PX - right_margin - page_text_width, A4_HEIGHT_PX - bottom_margin - line_height),
            page_text,
            font=font,
            fill="black"
        )

        # Send page to printer
        hdc.StartPage()
        dib = ImageWin.Dib(image)
        dib.draw(hdc.GetHandleOutput(), (0, 0, A4_WIDTH_PX, A4_HEIGHT_PX))
        hdc.EndPage()

    hdc.EndDoc()
    hdc.DeleteDC()
    win32print.ClosePrinter(hprinter)