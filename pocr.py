import os
import subprocess
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
import time
import shutil
from tqdm import tqdm

# --- ANSI ΧΡΩΜΑΤΑ ---
GREEN = "\033[92m"
RED = "\033[91m"
CYAN = "\033[96m"
YELLOW = "\033[93m"
RESET = "\033[0m"

# --- ΡΥΘΜΙΣΕΙΣ ---
THREADS = 8  # Ασφαλές όριο για i9-11900/32GB RAM
LANGS = "ell+eng+fra+tur+ara"

# Εντοπισμός του wm.png στον ίδιο φάκελο με το script
WATERMARK_PATH = Path(__file__).parent / "wm.png"

def run_ocr_task(img_path):
    env = os.environ.copy()
    env["OMP_THREAD_LIMIT"] = "1" # Αποφυγή CPU contention
    
    base_name = img_path.stem
    folder = img_path.parent
    output_base = str(folder / base_name)
    
    try:
        # 1. OCR (Tesseract -> ALTO XML)
        subprocess.run([
            "tesseract", str(img_path), output_base, 
            "-l", LANGS, "alto"
        ], env=env, capture_output=True, check=True)
        
        # 2. WATERMARK (ImageMagick Composite)
        wm_status = f"{YELLOW}Skipped{RESET}"
        if WATERMARK_PATH.exists():
            subprocess.run([
                "composite", "-dissolve", "15%", "-gravity", "center", 
                str(WATERMARK_PATH), str(img_path), str(img_path)
            ], check=True, capture_output=True)
            wm_status = f"{GREEN}Applied{RESET}"
        
        # 3. VIPS (Μετατροπή σε Tiled Pyramid TIFF)
        output_tif = str(folder / f"{base_name}.tif")
        subprocess.run([
            "vips", "tiffsave", str(img_path), output_tif,
            "--tile", "--pyramid", "--compression", "jpeg", "--Q", "85"
        ], check=True, capture_output=True)
        
        return True, f"{img_path.name} | OCR: {GREEN}OK{RESET} | WM: {wm_status} | TIFF: {GREEN}OK{RESET}"
    except Exception as e:
        return False, f"{RED}FAILED: {img_path.name} -> {str(e)}{RESET}"

def main():
    start_time = time.time()
    
    # Αρχικός έλεγχος για το Watermark
    if not WATERMARK_PATH.exists():
        print(f"{RED}⚠️  ΣΦΑΛΜΑ: Το {WATERMARK_PATH.name} δεν βρέθηκε στο {WATERMARK_PATH.parent}{RESET}")
    else:
        print(f"{GREEN}✅ Το Watermark εντοπίστηκε και θα εφαρμοστεί.{RESET}")

    # Εύρεση όλων των JPG (αναδρομικά)
    images = sorted(list(Path.cwd().rglob('*.jpg')) + list(Path.cwd().rglob('*.JPG')))
    
    if not images:
        print(f"{RED}❌ Δεν βρέθηκαν αρχεία JPG.{RESET}")
        return

    print(f"{CYAN}>>> Έναρξη επεξεργασίας {len(images)} αρχείων με {THREADS} threads...{RESET}\n")

    # 
    with tqdm(total=len(images), desc="Πρόοδος", unit="img", bar_format="{l_bar}{bar:30}{r_bar}") as pbar:
        with ProcessPoolExecutor(max_workers=THREADS) as executor:
            future_to_img = {executor.submit(run_ocr_task, img): img for img in images}
            
            for future in as_completed(future_to_img):
                success, message = future.result()
                tqdm.write(message) # Εκτύπωση κατάστασης για κάθε αρχείο
                pbar.update(1)

    # Οργάνωση αρχείων
    print(f"\n{YELLOW}>>> Οργάνωση τελικών αρχείων σε φακέλους tif/xml...{RESET}")
    for folder in set(img.parent for img in images):
        (folder / "tif").mkdir(exist_ok=True)
        (folder / "xml").mkdir(exist_ok=True)
        
        for f in folder.glob('*.tif'): shutil.move(str(f), str(folder / "tif" / f.name))
        for f in folder.glob('*.xml'): shutil.move(str(f), str(folder / "xml" / f.name))
        for f in folder.glob('*.jpg'): f.unlink()
        for f in folder.glob('*.JPG'): f.unlink()

    total_time = round(time.time() - start_time, 2)
    print(f"\n{GREEN}{'='*60}{RESET}")
    print(f"{GREEN}🏁 ΟΛΟΚΛΗΡΩΘΗΚΕ ΣΕ {total_time} ΔΕΥΤΕΡΟΛΕΠΤΑ{RESET} \a")

if __name__ == "__main__":
    main()