"""Publica o app: injeta o catálogo no index.html e copia os arquivos para o nginx."""
import json, os, shutil
H = os.path.dirname(os.path.abspath(__file__)); OUT = "/var/www/app-exemplo/checklist"
cat = json.dumps(json.load(open(f"{H}/checklists.json", encoding="utf8")), ensure_ascii=False).replace("</", "<\\/")
os.makedirs(OUT, exist_ok=True)
for f in os.listdir(f"{H}/web"):
    src, dst = f"{H}/web/{f}", f"{OUT}/{f}"
    if f == "index.html":
        t = open(src, encoding="utf8").read(); assert t.count("const CAT0 = [];") == 1
        open(dst, "w", encoding="utf8").write(t.replace("const CAT0 = [];", "const CAT0 = " + cat + ";"))
    else:
        shutil.copy(src, dst)
print("publicado em", OUT)
