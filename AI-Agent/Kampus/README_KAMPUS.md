# Top Eleven Kampus AI Agent

Pokreni `Pokreni Kampus Agent.cmd` dok je Top Eleven otvoren, zatim pritisni `POKRENI`.

Tok:

1. Otvori bocni meni, ceka 2 sekunde, klikne `Kampus`, zatim ceka sigurnosne 3 sekunde da se ekran ucita.
2. Potvrdi Kampus i klikne vizuelno pronadjenu lijevu ikonu alata.
3. Gemini pregleda procente i bira naziv objekta ispod 100%. Odluka da vise nema takvih objekata i dalje mora biti potvrdena kroz dva svjeza skeniranja.
4. Kampus kamera se stalno pomjera, zato se stara AI koordinata ne klika. Nakon Gemini odgovora agent odmah uzima svjezu sliku, projektivno poravna mapu i klikne unaprijed sigurnu unutrasnju tacku izabranog objekta. Ako poravnanje, najmanje tri zelene procentne oznake ili svjezi maintenance ekran nisu potvrdeni, nema klika. Poslije klika provjerava da li se detalj stvarno otvorio i po potrebi radi novi siguran pokusaj, najvise tri puta.
5. U detalju objekta ceka do 180 sekundi da plava tipka stvarno sadrzi bijeli tekst `100%`; sama plava pozadina nije dovoljna.
6. Pokrene reklamu istim AI-only/Google Play tokom. Gemini redovno provjerava reklamne kontrole svakih 20.5 sekundi, dok wake mehanizam po potrebi moze odmah zatraziti dodatnu provjeru.
7. Nakon potvrdenog povratka u Top Eleven klikne sigurnu zonu ispod bustera da zatvori detalj.
8. Ponavlja dok dvije svjeze Gemini provjere ne potvrde da su svi vidljivi objekti na 100%.

Tokom AI snimanja i klika prozor agenta se privremeno postavlja iza BlueStacksa, tako da ne moze prekriti objekat. Sigurnosni limit je 12 objekata po pokretanju. Vrijeme otvaranja Kampusa podesava se kroz `campusOpenBufferMs`, cekanje detalja kroz `campusDetailOpenWaitSeconds`, broj pokusaja kroz `campusBuildingClickAttempts`, a cekanje `100%` kroz `campusHundredButtonWaitSeconds` u roditeljskom `config.json`. Campus poravnanje radi samo nad mapom, bez fiksnog univerzalnog pomaka koordinata, i fail-closed je: ako kvalitet transformacije nije dovoljan, agent ne klikce.
