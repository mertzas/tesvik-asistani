"""
Teşvik Asistanı - Real Database (157 teşvik)
"""
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import sqlite3
import os

app = FastAPI(title="Teşvik Asistanı")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class AskRequest(BaseModel):
    question: str

DB_PATH = "data/tesvikler.db"

def get_tesvikler():
    """Load real incentives from SQLite database"""
    try:
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute('SELECT kurum, baslik, ozet, detay, hedef_kitle, kaynak_url FROM tesvikler')
        rows = cursor.fetchall()
        conn.close()

        tesvikler = []
        for row in rows:
            ozet = (row["ozet"] or "").strip()
            if len(ozet) > 150:
                ozet = ozet[:150] + "..."
            tesvikler.append({
                "kurum": row["kurum"] or "Devlet",
                "baslik": row["baslik"] or "Teşvik Programı",
                "ozet": ozet,
                "hedef_kitle": row["hedef_kitle"] or "Genel",
                "link": row["kaynak_url"] or "https://www.yatirimadestek.gov.tr"
            })
        return tesvikler
    except Exception as e:
        print(f"Database hatası: {e}")
        return []

TESVIKLER = get_tesvikler()

def normalize_turkish(text):
    """Normalize Turkish characters for search"""
    replacements = {'ç': 'c', 'Ç': 'C', 'ğ': 'g', 'Ğ': 'G', 'ı': 'i', 'İ': 'i', 'ö': 'o', 'Ö': 'O', 'ş': 's', 'Ş': 'S', 'ü': 'u', 'Ü': 'U'}
    for tr, eng in replacements.items():
        text = text.replace(tr, eng)
    return text

@app.get("/")
async def root():
    return HTMLResponse('''<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0"><title>Teşvik Asistanı</title>
<style>*{margin:0;padding:0;box-sizing:border-box}body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:linear-gradient(135deg,rgb(102,126,234) 0%,rgb(118,75,162) 100%);min-height:100vh;padding:20px}
.container{max-width:1000px;margin:0 auto}.header{background:white;padding:40px;border-radius:15px;margin-bottom:30px;box-shadow:0 10px 30px rgba(0,0,0,0.2);text-align:center}
.header h1{font-size:42px;color:rgb(102,126,234);margin-bottom:10px}.header p{font-size:16px;color:#666;margin-bottom:20px}
.search-section{background:white;padding:30px;border-radius:15px;margin-bottom:30px;box-shadow:0 10px 30px rgba(0,0,0,0.2)}
.search-box{display:flex;gap:10px;margin-bottom:20px}
.search-box input{flex:1;padding:15px 20px;border:2px solid #e0e0e0;border-radius:8px;font-size:16px;transition:border-color 0.3s}
.search-box input:focus{outline:none;border-color:rgb(102,126,234);box-shadow:0 0 0 3px rgba(102,126,234,0.1)}
.search-box button{padding:15px 40px;background:linear-gradient(135deg,rgb(102,126,234) 0%,rgb(118,75,162) 100%);color:white;border:none;border-radius:8px;font-weight:bold;font-size:16px;cursor:pointer;transition:all 0.3s}
.search-box button:hover{transform:translateY(-2px);box-shadow:0 10px 20px rgba(102,126,234,0.3)}
.results{display:grid;gap:15px}.result-card{background:#f9f9f9;padding:20px;border-radius:10px;border-left:4px solid rgb(102,126,234);transition:all 0.3s}
.result-card:hover{box-shadow:0 5px 15px rgba(0,0,0,0.1);transform:translateX(5px)}
.result-card .kurum{display:inline-block;background:rgb(102,126,234);color:white;padding:5px 12px;border-radius:4px;font-size:11px;font-weight:bold;text-transform:uppercase;margin-bottom:10px}
.result-card .baslik{font-size:18px;font-weight:bold;color:#333;margin-bottom:10px}.result-card .ozet{color:#666;font-size:14px;line-height:1.6;margin-bottom:10px}
.detay{background:#f0f4ff;padding:15px;border-radius:8px;font-size:13px;color:#444;line-height:1.8;margin:10px 0}
.no-results{text-align:center;padding:40px;color:#999}.loading{text-align:center;padding:30px}
.spinner{border:4px solid #f3f3f3;border-top:4px solid rgb(102,126,234);border-radius:50%;width:40px;height:40px;animation:spin 1s linear infinite;margin:0 auto 15px}
@keyframes spin{0%{transform:rotate(0deg)}100%{transform:rotate(360deg)}}
.info-box{background:#e8f4f8;border-left:4px solid rgb(102,126,234);padding:15px;border-radius:8px;margin-bottom:20px;font-size:14px;color:#333}
.tag{background:#f0f4ff;color:rgb(102,126,234);padding:8px 16px;border-radius:20px;cursor:pointer;font-size:14px;border:1px solid #e0e6ff;transition:all 0.3s;display:inline-block;margin:5px 5px 5px 0}
.tag:hover{background:rgb(102,126,234);color:white;transform:scale(1.05)}
.stats{margin-bottom:20px;padding:12px;background:#fff3cd;border-radius:6px;border-left:4px solid #ffc107;font-size:14px}
</style></head><body><div class="container">
<div class="header"><h1>🎯 Teşvik Asistanı</h1><p>Türkiye'nin Gerçek Devlet Teşvikleri (157+ Teşvik)</p></div>
<div class="search-section">
<div class="info-box">✅ GERÇEK VERİTABANI! 157 teşvik Türkiye Yatırım Destek Kurumundan yüklendi. Arama yaparak sonuçları göreceksin.</div>
<div class="search-box">
<input type="text" id="search-input" placeholder="Örn: Genel Teşvik, Bölgesel, Yatırım..." value="Teşvik" onkeypress="if(event.key==='Enter') performSearch()">
<button onclick="performSearch()">Ara</button>
</div>
<div style="margin-top:15px;"><strong>Hızlı Aramalar:</strong><br>
<div class="tag" onclick="search('Yatirim')">Yatırım</div>
<div class="tag" onclick="search('Bolgesel')">Bölgesel</div>
<div class="tag" onclick="search('Vergi')">Vergi</div>
<div class="tag" onclick="search('Tesvik')">Teşvik</div>
<div class="tag" onclick="search('Sanayi')">Sanayi</div>
</div>
</div>
<div id="results-container" class="results"></div>
</div>

<script>
async function performSearch(){const q=document.getElementById('search-input').value.trim();if(!q)return;await search(q)}
async function search(q){document.getElementById('search-input').value=q;const rc=document.getElementById('results-container');
rc.innerHTML='<div class="loading"><div class="spinner"></div><p>Aranıyor: <strong>'+q+'</strong></p></div>';
try{const r=await fetch('/api/sor',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({question:q})});
if(!r.ok)throw new Error('API Error: '+r.status);const d=await r.json();showResults(d.tesvikler||[],q)}
catch(e){rc.innerHTML='<div class="no-results">Hata: '+e.message+'</div>'}}
function showResults(rs,q=''){const rc=document.getElementById('results-container');if(!rs||rs.length===0){rc.innerHTML='<div class="no-results">Sonuç bulunamadı: '+q+'</div>';return}
const lim=rs.slice(0,20);const html=lim.map(t=>
'<div class="result-card"><div style="display:flex;justify-content:space-between;align-items:start"><div class="kurum">'+t.kurum+'</div><span style="background:#ffeaa7;color:#d63031;padding:4px 10px;border-radius:4px;font-weight:bold;font-size:12px">▼ '+lim.length+'/'+rs.length+'</span></div>'+
'<div class="baslik">'+t.baslik+'</div><div class="ozet">'+t.ozet+'</div><div class="detay"><strong>Hedef Kitle:</strong> '+t.hedef_kitle+'</div>'+
(t.link?'<a href="'+t.link+'" target="_blank" style="display:inline-block;margin-top:10px;padding:8px 16px;background:rgb(102,126,234);color:white;text-decoration:none;border-radius:5px;font-size:13px;font-weight:bold">🔗 Resmi Kaynak</a>':'')+
'</div>').join('');
rc.innerHTML='<div class="stats">Toplam <strong>'+rs.length+'</strong> sonuç bulundu. '+lim.length+' tane gösteriliyor.</div>'+html}
window.addEventListener('DOMContentLoaded',()=>search('Tesvik'))
</script>
</body></html>''')

@app.post("/api/sor")
async def ask_question(request: AskRequest):
    q = normalize_turkish(request.question.lower())
    results = []
    for tesvik in TESVIKLER:
        tesvik_text = normalize_turkish((tesvik["baslik"] + " " + tesvik["ozet"] + " " + tesvik["kurum"] + " " + tesvik["hedef_kitle"]).lower())
        if any(word in tesvik_text for word in q.split()):
            results.append(tesvik)
    return {"question": request.question, "tesvikler": results, "count": len(results)}

@app.get("/health")
async def health():
    return {"status": "ok", "tesvikler": len(TESVIKLER), "source": "data/tesvikler.db"}

if __name__ == "__main__":
    import uvicorn
    print(f"Yüklenen teşvik sayısı: {len(TESVIKLER)}")
    uvicorn.run(app, host="0.0.0.0", port=8000)
