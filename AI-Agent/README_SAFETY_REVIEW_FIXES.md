# Dorade nakon pregleda propusta

Implementirane su stavke 1, 2, 3, 4, 6 i 7. Stavka 5 nije proširena: Kampus i dalje čeka tačno 5 sekundi nakon potvrđenog povratka, prije postojećeg nastavka.

- Trening recognizer odbija preslabe podudarnosti i prazne slike. IZVJEŠTAJI, PONOVI, početak i završni X treninga potvrđuju se lokalnim traženjem referentnog izgleda dugmeta, ne samo fiksnom koordinatom.
- Lokalni povratak u TV/priručnik, trening i Put saveza prihvata prethodno potvrđen odlazak u Store/Chrome kao alternativu AI snimku reklame, kao Kampus. Svaki tok i dalje zahtijeva svoj povratni ekran. Ponovni ulazak u vanjsku aplikaciju resetuje niz stabilnih povratnih frameova.
- Čekanje zelenih/trening ponuda ponavlja AI klasifikaciju i kada je ranije viđeno plavo BESPLATNO, ali lokalna provjera nije uspjela. Prelaz na sivo ili ograničenje zato se ne gubi u zasebnom lokalnom čekanju. Odsustvo dugmeta ostaje nepoznato stanje.
- Kampus pokušava alternativno sporije povlačenje ako se traka nije pomjerila. Za dokaz kraja zahtijeva pomjeranje u suprotnom smjeru i povratak na iste kartice (pozicije i vizuelne potpise). Zaglavljena traka ili izgubljen fokus izazivaju grešku, ne lažni uspjeh.
- Back ima ukupan limit šest pokušaja po reklamnom kontekstu, ne resetuje ga novi klik/restore epizoda. Tri uzastopna Back pokušaja bez promjene slike prekidaju vanjsku navigaciju ranije.
- Hard recovery zavisi od `Exception.Data['AgentFailureKind']`, uključujući unutrašnje izuzetke. Sam tekst poruke nikad ne aktivira restart. `AdTimeout`, `AdCloseFailed` i `ExternalReturnTimeout` dozvoljavaju stari hard recovery; `ExternalNavigationStuck`, `ScreenUnknown`, `FocusLost` i `CampusBoundaryUnknown` ne dozvoljavaju ga.

Validacija uključuje referentne slike, crne/bijele/nasumične slike, uklonjen X, skalirane prikaze i simulirane PowerShell tokove. Ovo nije zamjena za provjeru uživo na novim reklamnim formatima.
