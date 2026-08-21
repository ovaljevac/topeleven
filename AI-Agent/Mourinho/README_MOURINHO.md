# Mourinho AI agent

Pokreni `Pokreni Mourinho Agent.cmd` dok je Top Eleven otvoren na glavnom ekranu.

Tok automatizacije:

1. Potvrdi glavni ekran prema `1.png`.
2. Posalje Gemini AI-u trenutni BlueStacks screenshot i trazi centar male kvadratne tipke desno od `Nivo spremnosti` progress bara i lijevo od `PREGLED UTAKMICE`. AI lokacija se koristi bez OpenCV odluke o tom dugmetu; dozvoljene su samo koordinate unutar readiness zone.
3. Potvrdi Mourinho prozor prema `2.png`.
4. Do 30 sekundi ceka plavo dugme koje mora sadrzavati prepoznatljiv `POGLEDAJ` tekst/ikonu. Obican plavi pravougaonik se ne prihvata.
5. Pokrene reklamu i koristi isti OpenCV + Gemini AI tok za X, skip i Google Play kao TV agent.
6. Zavrsava kada tri uzastopne provjere potvrde gornju Top Eleven traku resursa (tokeni, zeleni, plavi i crveni resursi). Mourinho prozor se nakon reklame ne zahtijeva.

Izmedju bitnih klikova koristi se sigurnosni buffer od 1500 ms.
