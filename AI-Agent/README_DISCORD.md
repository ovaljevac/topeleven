# Discord kontrola Top Eleven agenta

Bot moze pokrenuti samo unaprijed dozvoljene Top Eleven tokove. Ne prihvata proizvoljne terminalske komande.

## 1. Napravi Discord aplikaciju

1. Otvori Discord Developer Portal i napravi **New Application**.
2. U odjeljku **Bot** napravi bot i kopiraj njegov token. Token nikome ne salji i ne stavljaj ga u Git.
3. U **OAuth2 > URL Generator** oznaci `bot` i `applications.commands`.
4. Bot permissions: `View Channels`, `Send Messages` i `Use Slash Commands`.
5. Otvori generisani URL i dodaj bota na svoj server.

Message Content Intent nije potreban jer bot koristi slash komande.

## 2. Konfigurisi pristup

Najlakse je dvokliknuti `Postavi Discord Bot.cmd`. Otvorit ce tri prozora za token, Server ID i User ID te sam napraviti konfiguraciju.

Kopiraj `discord_config.example.json` u `discord_config.json`, pa unesi:

- `token`: bot token iz Developer Portala
- `guild_id`: ID Discord servera (komande se tako pojave odmah)
- `allowed_user_ids`: tvoj Discord User ID; mozes dodati jos ID brojeva
- `live_log`: `true` ako zelis automatske poruke iz loga

Za kopiranje ID-a ukljuci **Discord Settings > Advanced > Developer Mode**, zatim desni klik na server/korisnika i **Copy ID**.

## 3. Instaliraj i pokreni

Ako `python --version` ne radi, prvo instaliraj aktuelni Python 3 sa python.org i tokom instalacije oznaci **Add Python to PATH**.

U PowerShellu, iz `AI-Agent` foldera:

```powershell
python -m pip install -r requirements.txt
```

Zatim dvoklikni `Pokreni Discord Bot.cmd`. Taj prozor mora ostati otvoren dok koristis bota.

## Komande

- `/skripte` — prikazuje dozvoljene tokove
- `/pokreni` — bira i pokrece tok
- `/sve`, `/zeleni`, `/odmor`, `/tv`, `/mourinho`, `/kampus`, `/savez`, `/trening` — odmah pokrecu trazeni tok bez dodatnog izbora i klika
- `/restart` — potpuno gasi konfiguriranu BlueStacks instancu, ponovo pokrece Top Eleven i ceka potvrdu pocetnog ekrana
- `/start` — pokrece Top Eleven ako je zatvoren; ako vec radi, samo ga prebacuje u prvi plan
- `/status` — prikazuje aktivni tok i trajanje
- `/log` — zadnjih 20 redova loga
- `/stop` ili `/zaustavi` — salje postojeci sigurni stop signal agentu

Bot namjerno dozvoljava samo jednu aktivnu skriptu jer svi tokovi kontrolisu istu BlueStacks instancu.
