# Top Eleven kompletni AI agent

Pokreni `Pokreni AI Agent.cmd`, izaberi `Pokreni sve`, odaberi pocetnu fazu i pritisni `POKRENI AGENTA`. Stari direktni launcher `Pokreni sve redom.cmd` i dalje pokrece puni redoslijed od Mourinho faze.

Redoslijed je:

1. Mourinho reklama.
2. Top Eleven TV reklame.
3. Put saveza dnevna reklama.
4. Kampus objekti ispod 100%.
5. Uzmi 25 zelenih (`Zeleni` tok).

Kod obicne AI ili vizuelne neizvjesnosti agent ne gasi igru nego ponavlja sigurnu provjeru na istom koraku. Tvrdi restart tacne BlueStacks instance koristi se samo kada je reklama potvrdeno zaglavljena ili kada je prije nastavka potreban provjeren pocetni ekran. Neuspjela faza se zapisuje u log, nakon sigurnog preflighta prelazi se na sljedecu fazu, a Manager zavrsetak prikazuje kao upozorenje `Zavrseno uz greske`. Dugme `ZAUSTAVI` prekida cijeli zajednicki tok.

Ako reklama otvori Google Play Store ili Chrome, agent preko trenutnog BlueStacks ADB activity stanja salje Android Back, vraca se u reklamu i zavrsava njen X. Sljedeca faza ne dobija pravo na klik dok `MainPlayerNativeActivity` i Top Eleven zaglavlje nisu stabilno potvrdeni.

Postojeci pojedinacni launcheri i dalje rade nepromijenjeno.
