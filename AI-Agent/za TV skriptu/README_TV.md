# Top Eleven TV AI Agent

Pokreni Top Eleven i ostavi ga na pocetnom ekranu kao na `1.png`, zatim dvoklikni `Pokreni TV Agent.cmd` i pritisni `POKRENI`.

Tok:

1. Otvori bocni meni, ceka 2 sekunde, pritisne `Pocetni`, pa ponovo ceka 2 sekunde.
2. Potvrdi pocetni ekran, vizuelno pronadje bijelu monitor/play TV ikonu u gornjoj traci i klikne njen stvarni centar. Ne koristi fiksnu X koordinatu, jer sirina brojeva resursa pomjera TV dugme.
3. Na TV ekranu prihvata dugme samo kada istovremeno vidi odgovarajuci plavi pravougaonik i bijeli uzorak ikone/teksta `POGLEDAJ`; sama plava boja nije dovoljna. Dugmad obradjuje slijeva nadesno.
4. Reklame koriste isti potpuno AI-only tok iz glavnog agenta: prva Gemini provjera je nakon 5 sekundi, zatim svakih 16 sekundi, a wake dodir pokrece provjeru odmah.
5. Za `PRIRUCNIK` potvrdi ekrane 3, 4 i 5, izvrsi dva pojedinacna dodira i zatim klikne `NASTAVI`. Dinamicki detektor prepoznaje zeleni button sa stvarnim bijelim tekstom bez obzira zauzima li dio ili skoro cijelu sirinu; postojeca referentna koordinata ostaje kao drugi recognizer/fallback.
6. Zaustavlja se tek nakon najmanje 30 neprekidnih sekundi bez dostupnog `POGLEDAJ` dugmeta. Pojava bilo kojeg validnog dugmeta resetuje taj timer (`tvWatchButtonWaitSeconds` u roditeljskom `config.json`).

Izmedju uvodnih klikova na bocni meni i `Pocetni` postoji buffer od 2000 ms (`tvNavigationBufferMs`). Ostali navigacijski klikovi koriste 1500 ms (`tvClickBufferMs`), uz dodatno cekanje da detektor potvrdi sljedeci ekran.

Reference `1.png` do `5.png` ostaju u ovom folderu i koriste se samo za lokalnu klasifikaciju ekrana.
