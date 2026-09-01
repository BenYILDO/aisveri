'use strict';

/**
 * ÖSYM duyurular sayfasını çekip local bir JSON dosyasına kaydeder.
 * Electron main process içinde kullanılmak üzere yazıldı — dış sunucu,
 * webhook ya da GitHub Actions'a ihtiyaç duymaz.
 *
 * Bağımlılık: cheerio  ->  npm install cheerio
 * (fetch, Electron'un bundle ettiği Node sürümünde zaten mevcuttur; Node < 18
 *  kullanıyorsanız `npm install node-fetch` ekleyip aşağıdaki require'ı açın.)
 */

const fs = require('fs');
const path = require('path');
const cheerio = require('cheerio');
// const fetch = require('node-fetch'); // Node < 18 için

const SOURCE_URL = 'https://www.osym.gov.tr/duyurular/index';
const MAX_ANNOUNCEMENTS = 20;
const REQUEST_TIMEOUT_MS = 30_000;
const HEADERS = {
  'User-Agent':
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 ' +
    '(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36',
};

async function fetchAnnouncements() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), REQUEST_TIMEOUT_MS);

  let html;
  try {
    const response = await fetch(SOURCE_URL, { headers: HEADERS, signal: controller.signal });
    if (!response.ok) {
      throw new Error(`HTTP ${response.status} ${response.statusText}`);
    }
    html = await response.text();
  } finally {
    clearTimeout(timeout);
  }

  const $ = cheerio.load(html);
  const announcements = [];

  // Sayfa, arama kutusu için görünmeyen çok sayıda eski duyuruyu da DOM'a
  // gömüyor (bir seferinde 343 kayıt gelmişti); sadece en güncel N tanesini alıyoruz.
  $('a.duyuru-list-item').each((_, el) => {
    const $el = $(el);
    const href = ($el.attr('href') || '').trim();
    if (!href) return;

    const title = ($el.find('.duyuru-list-title').first().text() || $el.attr('title') || '').trim();
    const day = $el.find('.duyuru-list-day').first().text().trim();
    const monthYear = $el.find('.duyuru-list-my').first().text().trim();

    announcements.push({
      id: href,
      title,
      date: `${day} ${monthYear}`.trim(),
      url: new URL(href, SOURCE_URL).toString(),
    });
  });

  return announcements.slice(0, MAX_ANNOUNCEMENTS);
}

function saveAnnouncements(announcements, storageFile) {
  fs.mkdirSync(path.dirname(storageFile), { recursive: true });

  const payload = {
    updated_at: new Date().toISOString(),
    source: SOURCE_URL,
    count: announcements.length,
    announcements,
  };

  // Her seferinde aynı dosyanın üzerine yazılır (append değil) — dosya büyümez.
  const tmpFile = `${storageFile}.tmp`;
  fs.writeFileSync(tmpFile, JSON.stringify(payload, null, 2), 'utf-8');
  fs.renameSync(tmpFile, storageFile);

  return payload;
}

function loadAnnouncements(storageFile) {
  if (!fs.existsSync(storageFile)) {
    return { updated_at: null, source: SOURCE_URL, count: 0, announcements: [] };
  }
  return JSON.parse(fs.readFileSync(storageFile, 'utf-8'));
}

/** Tek seferlik: sayfayı çeker, storageFile'a kaydeder, kaydedilen veriyi döner. */
async function checkAnnouncementsOnce(storageFile) {
  const announcements = await fetchAnnouncements();
  return saveAnnouncements(announcements, storageFile);
}

/**
 * Her gün belirtilen saatte (varsayılan 10:00, local saat) checkAnnouncementsOnce'ı
 * çalıştırır. Ek bir paket (node-cron vb.) gerektirmez. Electron main process'te
 * app.whenReady() içinden çağırın. Dönen fonksiyon zamanlayıcıyı durdurur.
 */
function scheduleDaily(storageFile, { hour = 10, minute = 0, onResult, onError } = {}) {
  let timeoutId = null;

  const runAndReschedule = async () => {
    try {
      const result = await checkAnnouncementsOnce(storageFile);
      onResult?.(result);
    } catch (err) {
      onError?.(err);
    } finally {
      timeoutId = setTimeout(runAndReschedule, msUntilNext(hour, minute));
    }
  };

  timeoutId = setTimeout(runAndReschedule, msUntilNext(hour, minute));
  return () => clearTimeout(timeoutId);
}

function msUntilNext(hour, minute) {
  const now = new Date();
  const next = new Date(now.getFullYear(), now.getMonth(), now.getDate(), hour, minute, 0, 0);
  if (next <= now) next.setDate(next.getDate() + 1);
  return next.getTime() - now.getTime();
}

module.exports = {
  SOURCE_URL,
  MAX_ANNOUNCEMENTS,
  fetchAnnouncements,
  saveAnnouncements,
  loadAnnouncements,
  checkAnnouncementsOnce,
  scheduleDaily,
};
