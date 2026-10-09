# CONVERT. v2 — betrouwbare conversie en betere foutdiagnose

## Wat is nieuw?

- Spotify-links geven bij een mislukte titelherkenning meteen de optie om op artiest/titel te zoeken. Er wordt **geen Spotify-audiostream gedownload**.
- Een directe YouTube-link wordt voortaan op basis van het video-ID herkend, ook wanneer de server de videometadata niet kan ophalen.
- Foutcodes leggen uit of de YouTube-server weigert (YOUTUBE_BLOCKED), de video beperkt is, een netwerkfout is ontstaan of de conversie zelf mislukte.
- Na een mislukte download zie je de optie om je eigen bestand te uploaden.
- Een lokale serveroptie is toegevoegd, zodat je CONVERT. vanaf een computer in hetzelfde wifi-netwerk kunt draaien. Een thuisnetwerk wordt doorgaans minder snel als datacenter-IP gezien, maar YouTube-downloads zijn ook dan niet gegarandeerd.
- De server herhaalt de volledige YouTube-metadataaanvraag niet meer voordat hij begint met downloaden; er is nu één downloadpassage en zichtbare voortgang waar YouTube dit levert.

## Welke onderdelen zijn echt getest?

De MP3- en FLAC-conversie van **geüploade bestanden** is lokaal getest met FFmpeg. Voor YouTube zijn de URL-herkenning, de foutmeldingen en de job-flow met een **mock** getest. Het ophalen van auteursrechtelijk beschermd of beschermd platformmateriaal is niet getest en wordt niet gegarandeerd.

## Route A — gratis Render-cloudserver bijwerken

1. Download `CONVERT-v2-Render.zip` en pak uit.
2. Vervang in dezelfde GitHub-repository van v1 de bestanden: `app.py`, `index.html`, `requirements.txt`, `Dockerfile`, `render.yaml` en `README-NL.md`. Commit.
3. Render voert automatisch een herdeploy uit als automatisch deployen aanstaat; anders kies *Manual Deploy*.
4. Wacht tot je site online is en open de site in Safari. Onder *Instellingen* staat de backendversie en de versie van yt-dlp.
5. Test een video die je mag downloaden. Bij een fout krijg je nu een code en concrete uitleg.

**Belangrijk:** dit verhelpt niet automatisch een YouTube-blokkade op het Render-IP-adres. Je kunt dit ook niet betrouwbaar oplossen door steeds een ander nummer te kiezen.

## Route B — gratis lokale conversieserver (Windows of Mac)

Dit is de aanbevolen optie als Render consequent geblokkeerd wordt. Je hebt een computer met Docker Desktop en een wifi-netwerk nodig. De computer moet tijdens het omzetten aanstaan.

1. Installeer/start [Docker Desktop](https://www.docker.com/products/docker-desktop/) (gratis voor persoonlijk gebruik onder de toepasselijke licentievoorwaarden).
2. Pak `CONVERT-v2-Lokaal.zip` uit op je computer.
3. **Windows:** dubbelklik `START-WINDOWS.bat`. **Mac:** rechtsklik `START-MAC.command` en kies Open; bevestig indien gevraagd.
4. Wacht tot de Docker-image klaar is. Op je computer kun je `http://localhost:8765` openen.
5. Zoek het lokale IP-adres van je computer. Windows: opdrachtprompt `ipconfig` en kijk bij *IPv4-adres*. Mac: het startscript toont meestal het lokale IP-adres.
6. Open Safari op je iPhone, **op dezelfde wifi**, met `http://<IP-VAN-JE-COMPUTER>:8765`. Voorbeeld: `http://192.168.1.25:8765`.
7. Upload je eigen bestand of gebruik een bron waarvan de download is toegestaan; kies MP3 of FLAC.

De telefoon praat via wifi met je eigen computer. Je hoeft geen Render-credits te gebruiken en het werkgeheugen van je iPhone wordt niet belast met de conversie. Als YouTube ook op je eigen netwerk blokkeert, blijft uploaden van bestanden het betrouwbare alternatief.

**Privacy:** de lokale server is bereikbaar voor apparaten op hetzelfde netwerk zolang Docker draait. Gebruik dit niet op een openbaar wifi-netwerk en zet geen port-forwarding aan op je router. De app heeft geen ingebouwde gebruikerslogin. Stop Docker als je klaar bent.

## Spotify / YouTube

Spotify ondersteunt via de officiële API geen downloaden van volledige songs. Spotify-links worden alleen gebruikt voor metadata en de titelzoekopdracht. YouTube staat niet toe dat een app via de YouTube-API de audio uit video's downloadt of scheidt. Gebruik CONVERT. alleen voor materiaal waarvoor je de benodigde rechten en toestemming hebt. Persoonlijk gebruik op zichzelf verleent die toestemming niet.

## Formaten

- MP3: 320 kbps, stereo, 44,1 kHz.
- FLAC: 24-bit, stereo, 44,1 kHz. De encoding is verliesvrij ten opzichte van het gedecodeerde signaal, maar verhoogt de kwaliteit van MP3 of YouTube-audio niet.
- Maximaal 90 MB per upload en 12 minuten per opname. Eén conversie tegelijk op de gratis server.
- Resultaten worden automatisch na circa 30 minuten verwijderd of bij herstart van de server.

## Benodigd

- `Dockerfile`, `app.py`, `requirements.txt`, `index.html` vormen de complete server/webapp.
- `render.yaml` gebruikt het Render Free-plan.
- `compose.yaml`, `START-WINDOWS.bat`, `START-MAC.command` bieden de lokale Docker-route.
