## SBH Kørsel – Kontrol af hjælpemiddel i Nexus

Automatisering der kontrollerer, om en borger allerede har et godkendt hjælpemiddel registreret i KMD Nexus, som led i behandlingen af en ny XFlow-ansøgning om hjælpemiddel.

## Hvad gør robotten?

1. **Henter igangværende processer** fra XFlow med processkabelon-id `753`, der afventer RPA-integration (`RPAIntegration`-aktivitet)
2. **Udtrækker CPR-nummer** fra blanketten _"SBH – Samlet"_ for hver proces
3. **Fylder arbejdskøen** med procesid og CPR-nummer
4. **Slår borgeren op** i KMD Nexus via CPR-nummer
5. **Henter borgerens udlån** fra Nexus og filtrerer på godkendte hjælpemiddelkategorier (kørestole, rollatorer, ganghjælpemidler m.fl.)
6. **Henter borgerens skemaer** af typen _"Samlet faglig vurdering"_ og finder eventuelle godkendte hjælpemidler
7. **Sender resultatet tilbage** til XFlow-processen med oplysninger om fundne udlån og skemaer
8. **Avancerer processen** i XFlow, så sagsbehandleren kan fortsætte

## Forudsætninger

- Python ≥ 3.13
- [`uv`](https://docs.astral.sh/uv/) til pakkehåndtering
- Adgang til **Automation Server** (arbejdskø)
- Adgang til **KMD Nexus** (produktion)
- Adgang til **XFlow** (produktion)
- En **Odense SQL Server**-konto til aktivitetssporing

## Installation

```sh
uv sync
```

## Konfiguration

Kopiér `.env.example` til `.env` og udfyld følgende:

| Variabel | Beskrivelse |
|---|---|
| `ATS_URL` | URL til Automation Server API |
| `ATS_TOKEN` | API-token til Automation Server |

Legitimationsoplysninger til Nexus, XFlow og SQL Server hentes fra **Automation Server Credentials** under følgende navne:

| Credential-navn | Anvendelse |
|---|---|
| `KMD Nexus - produktion` | Autentifikation mod KMD Nexus |
| `Xflow - produktion` | Autentifikation mod XFlow |
| `Odense SQL Server` | Aktivitetssporing |

## Kørsel

```sh
# Fyld arbejdskøen med igangværende XFlow-processer
uv run python main.py --queue

# Behandl arbejdskøen
uv run python main.py
```

### Argumenter

| Argument | Beskrivelse |
|---|---|
| `--queue` | Fyld arbejdskøen og afslut (kør ingen behandling) |

## Afhængigheder

| Pakke | Formål |
|---|---|
| `automation-server-client` | Arbejdskø-håndtering |
| `kmd-nexus-client` | Integration med KMD Nexus |
| `xflow-client` | Integration med XFlow |
| `odk-tools` | Aktivitetssporing |

## Persondatasikkerhed

Robotten behandler følsomme personoplysninger på vegne af Odense Kommune, herunder **CPR-numre** (personnumre), der er fortrolige oplysninger, og **helbredsrelaterede oplysninger** fra hjælpemiddelskemaer (særlige kategorier jf. GDPR art. 9).

- Ingen personoplysninger må lægges i dette repository — hverken som testdata, i kode eller i kommentarer
- CPR-numre og øvrige persondata opbevares udelukkende i arbejdskøen på Automation Server og behandles i hukommelsen under kørsel — de persisteres ikke lokalt
- Legitimationsoplysninger håndteres udelukkende via miljøvariabler (`.env`) og Automation Server Credentials — aldrig i kode
- `.env`-filen er ekskluderet via `.gitignore` og må aldrig committes
- Adgang til Nexus og XFlow kræver tjenstlige konti med princippet om mindst nødvendige rettigheder

