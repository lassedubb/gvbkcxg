# CONVERT. v1 — gratis webapp

**CONVERT.** gebruikt jouw handgeschreven rode logo en de zwart-rode vormgeving van STEMS. en STRETCH.

## Wat werkt

- Een Spotify-tracklink herkennen via de officiële openbare Spotify oEmbed-dienst. De titel (en waar beschikbaar artiest) wordt gebruikt om YouTube-resultaten te zoeken. **Er wordt geen Spotify-audio gedownload.**
- Automatisch maximaal vijf YouTube-zoekresultaten tonen. Controleer en selecteer zelf de juiste video.
- YouTube-videolinks herkennen en, als het downloaden technisch en volgens jouw rechten is toegestaan, het audiospoor ophalen met yt-dlp.
- MP4/MOV/audio uploaden en als MP3 (320 kbps, 44,1 kHz) of FLAC (24-bit, 44,1 kHz) converteren met FFmpeg.
- Resultaat voorbeluisteren en downloaden.
- Vanaf iPhone Safari bedienen en een link naar je eigen STEMS. instellen.

## BELANGRIJK: één HTML is niet voldoende

Het YouTube-onderdeel vereist een echte Python-server waarop yt-dlp en FFmpeg draaien. De losse `index.html` heeft alleen de frontend. Zet de volledige app online op Render, of gebruik Cloudflare Pages **naast** de Render-server.

## Makkelijkste gratis publicatie: één site op Render

1. Download `CONVERT-v1-Render.zip` en pak het uit via de Bestanden-app op je iPhone of op je computer.
2. Maak een gratis repository op https://github.com/new, bijvoorbeeld `convert-app`.
3. Upload vanuit de uitgepakte map de vijf bestanden **`Dockerfile`, `app.py`, `requirements.txt`, `render.yaml`, `index.html`** en commit de bestanden. Ze moeten direct in de hoofdmap van je repository staan (niet in een extra submap).
4. Ga naar https://dashboard.render.com/ en maak een **New → Web Service** aan. Koppel de GitHub-repository.
5. Render hoort de `Dockerfile` te vinden. Kies het **Free**-plan. Deploy. Je kunt ook een Render Blueprint maken via `render.yaml`.
6. Wacht tot de build klaar is. Open daarna het `*.onrender.com`-adres in Safari.
7. Plak je Spotify- of YouTube-link, controleer de gevonden video, kies MP3/FLAC, vink aan dat je deze audio mag converteren en start de taak.

Render Free kan na 15 minuten zonder verkeer pauzeren. De eerste herstart kan ongeveer een minuut kosten. Bij intensief gebruik gelden gratis limieten. Het YouTube-gedeelte kan worden geblokkeerd door YouTube, vooral vanaf gedeelde hosting-IP-adressen. Dit is daarom **een te testen v1, geen garantie dat elke YouTube-link werkt**.

## Optioneel: Cloudflare Pages voor de voorkant

1. Zet de volledige backend hierboven eerst op Render online.
2. Upload `CONVERT-v1-Cloudflare-Pages.zip` naar Cloudflare Pages via de direct-uploadmethode. Dit archief bevat alleen `index.html`.
3. Open de Cloudflare-site en klap onderaan **Instellingen · Server & STEMS.** open.
4. Vul bij **API-server** het Render-adres in, bijvoorbeeld `https://convert-app.onrender.com` (zonder `/` op het einde), en sla op.
5. Vanaf nu communiceert Cloudflare Pages met de backend op Render. Ook hier gelden de Render-beperkingen voor YouTube-downloads.

## Voor de beste betrouwbaarheid

- Kies voor Spotify een losse *track*, niet een album of playlist.
- Controleer de YouTube-resultaten: de eerste automatische suggestie kan een live-, remix- of coverversie zijn.
- Spotify zelf is nooit de downloadbron.
- Upload voor gegarandeerdere verwerking het eigen videobestand in de **UPLOAD**-tab. Uploadconversie is lokaal getest met een echte MP4-video van 2:39.
- 24-bit FLAC voorkomt extra lossy compressie maar herstelt geen informatie uit een gecomprimeerde YouTube-bron.
- Deze gratis v1 accepteert maximaal één gelijktijdige verwerking, bestanden tot 90 MB en opnames tot 12 minuten. Resultaten verdwijnen na 30 minuten of een serverherstart.
- Het programma is bedoeld voor gebruik met toestemming of eigen/rechtenvrije media. YouTube en Spotify stellen eigen gebruiksvoorwaarden.

## Status van de tests

- **Echt geslaagd:** uploads van WAV en MP4, FFmpeg MP3-conversie, 24-bit FLAC, downloaden, audioformaat gecontroleerd met ffprobe.
- **Gesimuleerd geslaagd:** Spotify-resultaatscherm, automatisch YouTube-zoeken, selectie uit meerdere video's en job-flow met een nagebootste YouTube-downloader.
- **Nog te testen na Render-deploy:** bereikbaarheid Spotify oEmbed en YouTube vanuit de echte online server, daadwerkelijke yt-dlp-download en gebruik in iPhone Safari.

## Bestanden

- `index.html` — complete iPhone-interface met logo (alle afbeeldingen zitten ingebakken in de HTML).
- `app.py` — FastAPI-server voor Spotify-lookup, YouTube-zoeken, yt-dlp en FFmpeg.
- `requirements.txt` — Python-afhankelijkheden inclusief `yt-dlp[default]` en JavaScript-uitdagingsscripts.
- `Dockerfile` — installatie van Python, FFmpeg, Deno en de server op Render. Deno is nodig voor hedendaagse YouTube JavaScript-challenges.
- `render.yaml` — Render Blueprint, Free-plan.

