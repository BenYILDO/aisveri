# ÖSYM Duyuru Scraper

ÖSYM'nin duyurular sayfasını (`https://www.osym.gov.tr/duyurular/index`) periyodik olarak
çekip en güncel 20 duyuruyu local bir JSON dosyasına kaydeden, Electron uygulamalarına
gömülmek üzere yazılmış bağımsız bir Node modülü. Dışarıya (webhook, sunucu vb.) hiçbir
istek atmaz; her şey kendi bilgisayarınızda çalışır.

## Kurulum

1. `duyuru-scraper.js` dosyasını Electron projenizin içine kopyalayın (örn. `src/duyuru-scraper.js`).
2. Tek bağımlılığı kurun:
   ```bash
   npm install cheerio
   ```
   > Node 18+ / güncel Electron sürümleri `fetch`'i zaten dahili olarak sağlar, ekstra bir
   > paket gerekmez. Daha eski bir Node/Electron sürümü kullanıyorsanız `npm install node-fetch`
   > kurup dosyanın en üstündeki yorum satırını (`// const fetch = require('node-fetch');`) açın.

## Kullanım (Electron main process)

```js
const { app, ipcMain } = require('electron');
const path = require('path');
const {
  checkAnnouncementsOnce,
  loadAnnouncements,
  scheduleDaily,
} = require('./duyuru-scraper');

const storageFile = path.join(app.getPath('userData'), 'duyurular.json');

app.whenReady().then(() => {
  // Uygulama açılır açılmaz bir kez çek
  checkAnnouncementsOnce(storageFile).catch(console.error);

  // Uygulama açık kaldığı sürece her gün 10:00'da otomatik çek
  scheduleDaily(storageFile, {
    hour: 10,
    minute: 0,
    onResult: (data) => console.log('Duyurular güncellendi:', data.count),
    onError: (err) => console.error('Duyuru çekilemedi:', err),
  });
});

// Renderer (arayüz) tarafından veriyi okumak için IPC handler
ipcMain.handle('get-duyurular', () => loadAnnouncements(storageFile));
```

Renderer tarafında (preload + renderer):

```js
// preload.js
contextBridge.exposeInMainWorld('duyuruAPI', {
  getDuyurular: () => ipcRenderer.invoke('get-duyurular'),
});

// renderer.js
const { announcements, updated_at } = await window.duyuruAPI.getDuyurular();
```

## Davranış notları

- **Uygulama açıkken çalışır:** `scheduleDaily` bir arka plan servisi değildir; Electron
  uygulaması kapatılırsa zamanlayıcı da durur. Uygulama kapalıyken kaçırılan günleri telafi
  etmek istiyorsanız, yukarıdaki gibi `app.whenReady()` içinde her açılışta bir kez
  `checkAnnouncementsOnce()` çağırın — böylece uygulama en son ne zaman açıldıysa o anki
  güncel veriyi çeker.
- **Dosya büyümez:** Her çalıştırmada `storageFile` en fazla 20 kayıtla **üzerine yazılır**
  (append edilmez).
- **Manuel/anlık çekim** için `checkAnnouncementsOnce(storageFile)` fonksiyonunu istediğiniz
  yerden (örn. arayüzdeki bir "Yenile" butonuna bağlı IPC handler'dan) çağırabilirsiniz.

## API

| Fonksiyon | Açıklama |
|---|---|
| `fetchAnnouncements()` | Sayfayı çeker, parse eder, en güncel 20 duyuruyu dizi olarak döner. |
| `saveAnnouncements(list, storageFile)` | Verilen listeyi `storageFile`'a (üzerine yazarak) kaydeder. |
| `loadAnnouncements(storageFile)` | `storageFile`'daki son kaydı okur; dosya yoksa boş sonuç döner. |
| `checkAnnouncementsOnce(storageFile)` | `fetchAnnouncements` + `saveAnnouncements`'ı art arda çalıştırır. |
| `scheduleDaily(storageFile, opts)` | Her gün `opts.hour:opts.minute`'te `checkAnnouncementsOnce`'ı tetikler; durdurma fonksiyonu döner. |

## Veri formatı

```json
{
  "updated_at": "2026-09-01T07:00:00.000Z",
  "source": "https://www.osym.gov.tr/duyurular/index",
  "count": 20,
  "announcements": [
    {
      "id": "/2026-kpss-lisans-sinavi-...",
      "title": "2026-KPSS Lisans Sınavı Genel Yetenek-Genel Kültür Oturumu: Sınava Giriş Belgeleri Erişime Açıldı",
      "date": "27 Ağustos 2026",
      "url": "https://www.osym.gov.tr/2026-kpss-lisans-sinavi-..."
    }
  ]
}
```
