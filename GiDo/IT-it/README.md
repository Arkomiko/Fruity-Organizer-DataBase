<p align="center"><img src="banner.svg" alt="FODB" width="100%"></p>

<p align="center">
<a href="../../README.md"><img src="../../docs/lang/EN-en-off.svg" height="26" alt="English"></a>
<a href="../../GiDo/RU-ru/README.md"><img src="../../docs/lang/RU-ru-off.svg" height="26" alt="Русский"></a>
<a href="../../GiDo/ZH-cn/README.md"><img src="../../docs/lang/ZH-cn-off.svg" height="26" alt="简体中文"></a>
<a href="../../GiDo/ES-es/README.md"><img src="../../docs/lang/ES-es-off.svg" height="26" alt="Español"></a>
<a href="../../GiDo/HI-in/README.md"><img src="../../docs/lang/HI-in-off.svg" height="26" alt="हिन्दी"></a>
<a href="../../GiDo/FR-fr/README.md"><img src="../../docs/lang/FR-fr-off.svg" height="26" alt="Français"></a>
<a href="../../GiDo/BN-bd/README.md"><img src="../../docs/lang/BN-bd-off.svg" height="26" alt="বাংলা"></a>
<a href="../../GiDo/PT-br/README.md"><img src="../../docs/lang/PT-br-off.svg" height="26" alt="Português"></a>
<a href="../../GiDo/UR-pk/README.md"><img src="../../docs/lang/UR-pk-off.svg" height="26" alt="اردو"></a>
<a href="../../GiDo/ID-id/README.md"><img src="../../docs/lang/ID-id-off.svg" height="26" alt="Indonesia"></a>
<a href="../../GiDo/DE-de/README.md"><img src="../../docs/lang/DE-de-off.svg" height="26" alt="Deutsch"></a>
<a href="../../GiDo/JA-jp/README.md"><img src="../../docs/lang/JA-jp-off.svg" height="26" alt="日本語"></a>
<a href="../../GiDo/TR-tr/README.md"><img src="../../docs/lang/TR-tr-off.svg" height="26" alt="Türkçe"></a>
<a href="../../GiDo/KO-kr/README.md"><img src="../../docs/lang/KO-kr-off.svg" height="26" alt="한국어"></a>
<a href="../../GiDo/VI-vn/README.md"><img src="../../docs/lang/VI-vn-off.svg" height="26" alt="Tiếng Việt"></a>
<a href="../../GiDo/IT-it/README.md"><img src="../../docs/lang/IT-it-on.svg" height="26" alt="Italiano"></a>
<a href="../../GiDo/PL-pl/README.md"><img src="../../docs/lang/PL-pl-off.svg" height="26" alt="Polski"></a>
<a href="../../GiDo/UK-ua/README.md"><img src="../../docs/lang/UK-ua-off.svg" height="26" alt="Українська"></a>
<a href="../../GiDo/TH-th/README.md"><img src="../../docs/lang/TH-th-off.svg" height="26" alt="ไทย"></a>
<a href="../../GiDo/KK-kz/README.md"><img src="../../docs/lang/KK-kz-off.svg" height="26" alt="Қазақша"></a>
<a href="../../GiDo/UZ-uz/README.md"><img src="../../docs/lang/UZ-uz-off.svg" height="26" alt="Oʻzbekcha"></a>
<a href="../../GiDo/BE-by/README.md"><img src="../../docs/lang/BE-by-off.svg" height="26" alt="Беларуская"></a>
<a href="../../GiDo/AZ-az/README.md"><img src="../../docs/lang/AZ-az-off.svg" height="26" alt="Azərbaycanca"></a>
<a href="../../GiDo/HY-am/README.md"><img src="../../docs/lang/HY-am-off.svg" height="26" alt="Հայերեն"></a>
<a href="../../GiDo/ISV-sl/README.md"><img src="../../docs/lang/ISV-sl-off.svg" height="26" alt="Medžuslovjansky"></a>
<a href="../../GiDo/HE-il/README.md"><img src="../../docs/lang/HE-il-off.svg" height="26" alt="עברית"></a>
</p>

<p align="center"><a href="https://github.com/Arkomiko/Fruity-Organizer-DataBase/releases/latest"><b>⬇ Scarica FODB.exe</b></a> &nbsp;|&nbsp; <a href="https://arkomiko.github.io/Fruity-Organizer-DataBase/IT-it/wiki/index.html"><b>Wiki</b></a></p>

Un organizzatore portatile per il database dei plugin di FL Studio. Sistema i plugin in cartelle per produttore, per funzione o per entrambi, con un aspetto in armonia con FL Studio.

<p align="center"><img src="../../docs/demo-en.gif" alt="FODB" width="100%"></p>

## Funzionalità

- Ordina per produttore, per funzione o annida in qualsiasi ordine: Produttore\Funzione o Funzione\Produttore
- Riconosce a cosa serve ogni plugin: riverbero, EQ, dinamica, sintetizzatore e altre 18 funzioni
- Filtri per funzione, produttore, formato, bit, stato, data del file, dimensione e altro
- Segue il tema corrente di FL Studio in tempo reale
- Backup automatici, annullamento con un clic, nulla esce dalla cartella del database
- Un unico file da 10 MB senza installazione; le impostazioni restano accanto
- 26 lingue dell'interfaccia e impostazioni per disposizione, scorciatoie, scala, caratteri, colori e altro

## Avvio rapido

1. Scarica FODB.exe ed eseguilo. Il database dei plugin viene trovato automaticamente.
2. Scegli una disposizione delle cartelle e attiva sorgenti e filtri.
3. Premi «Organizza plugin», controlla l'anteprima, poi aggiorna il browser dei plugin in FL Studio.

## Disposizioni delle cartelle

<p align="center"><img src="workflow.svg" alt="Disposizioni delle cartelle" width="100%"></p>

Scegli un modello o scrivine uno tuo con queste parti:

```text
{vendor}  {purpose}  {format}  {bits}  {letter}  {kind}

{vendor}\{purpose}
{purpose}\{vendor}
USER\{format}\{vendor}
```

## Filtri

Spunta i valori nel menu Filtri o scrivi le condizioni nella casella di ricerca:

```text
purpose:reverb,delay                 reverb OR delay
vendor:"plugin alliance" -format:vst  one vendor, without VST2
organized:no kind:synth               synths not organized yet
age:30d bits:64                       64-bit, dated in the last 30 days
```

## Temi di FL Studio

<p align="center"><img src="themes.svg" alt="Temi di FL Studio" width="100%"></p>

FODB legge il tema attivo e aggiorna i colori quando lo cambi in FL Studio. I colori di base sono molto simili, ma non identici al pixel.

## Sicurezza

- I tuoi plugin non vengono mai modificati. Nella cartella Installed può cambiare solo l'elenco New: un plugin organizzato ne esce, e si può disattivare.
- Ogni operazione può essere annullata e i file rimossi finiscono nel Cestino.
- Prima di ogni modifica viene creato un backup ZIP del database; si conservano i 40 più recenti e il numero è regolabile.

## Regole personali

Aggiungi regole nella scheda Impostazioni o in FODB.json per definire l'uso per nome o produttore con espressioni regolari:

```json
"purpose_rules": [
  { "purpose": "drums", "name": "kick|808" },
  { "purpose": "vocal", "vendor": "antares" }
]
```

## Compilare dai sorgenti

Richiede Windows e Python 3.13. Il programma usa solo la libreria standard.

```powershell
./build.ps1
```

## Riconoscimenti

Basato su FL Studio Automatic Plugin Organizer di Magabes e collaboratori, con licenza MIT.

Progetto indipendente, non affiliato a Image-Line. FL Studio è un marchio di Image-Line.
