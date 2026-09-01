<?php
/**
 * ÖSYM duyuru webhook endpoint'i.
 *
 * POST: GitHub Actions'tan gelen {"announcements": [...], ...} gövdesini alır,
 *       en fazla MAX_ANNOUNCEMENTS kaydı storage/duyurular.json dosyasına
 *       YAZAR (append değil, üzerine yazar) — böylece dosya asla büyümez.
 * GET:  Şu an dosyada duran son kayıtları (en fazla MAX_ANNOUNCEMENTS) JSON
 *       olarak döner.
 *
 * Kimlik doğrulama yok; endpoint URL'ini bilen herkes erişebilir.
 */

declare(strict_types=1);

const MAX_ANNOUNCEMENTS = 20;
const STORAGE_FILE = __DIR__ . '/storage/duyurular.json';

header('Content-Type: application/json; charset=utf-8');

function respond(int $status, array $body): void
{
    http_response_code($status);
    echo json_encode($body, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES);
    exit;
}

function read_storage(): array
{
    if (!is_file(STORAGE_FILE)) {
        return [
            'updated_at' => null,
            'count' => 0,
            'announcements' => [],
        ];
    }

    $raw = file_get_contents(STORAGE_FILE);
    $data = json_decode($raw ?: '', true);

    if (!is_array($data) || !isset($data['announcements'])) {
        return [
            'updated_at' => null,
            'count' => 0,
            'announcements' => [],
        ];
    }

    return $data;
}

function write_storage(array $announcements, ?string $source): void
{
    $storageDir = dirname(STORAGE_FILE);
    if (!is_dir($storageDir)) {
        mkdir($storageDir, 0775, true);
    }

    $announcements = array_slice($announcements, 0, MAX_ANNOUNCEMENTS);

    $payload = [
        'updated_at' => gmdate('c'),
        'source' => $source,
        'count' => count($announcements),
        'announcements' => $announcements,
    ];

    $tmpFile = STORAGE_FILE . '.tmp';
    file_put_contents($tmpFile, json_encode($payload, JSON_UNESCAPED_UNICODE | JSON_UNESCAPED_SLASHES | JSON_PRETTY_PRINT), LOCK_EX);
    rename($tmpFile, STORAGE_FILE);
}

$method = $_SERVER['REQUEST_METHOD'] ?? 'GET';

if ($method === 'GET') {
    $data = read_storage();
    $data['announcements'] = array_slice($data['announcements'], 0, MAX_ANNOUNCEMENTS);
    $data['count'] = count($data['announcements']);
    respond(200, $data);
}

if ($method === 'POST') {
    $raw = file_get_contents('php://input');
    $body = json_decode($raw ?: '', true);

    if (!is_array($body) || !isset($body['announcements']) || !is_array($body['announcements'])) {
        respond(400, ['error' => 'Geçersiz gövde: "announcements" alanı bir dizi olmalı.']);
    }

    write_storage($body['announcements'], $body['source'] ?? null);

    respond(200, [
        'status' => 'ok',
        'saved' => count(array_slice($body['announcements'], 0, MAX_ANNOUNCEMENTS)),
    ]);
}

respond(405, ['error' => 'Yalnızca GET ve POST desteklenir.']);
