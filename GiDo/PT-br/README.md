<p align="center"><img src="banner.svg" alt="FODB" width="100%"></p>

<p align="center">
<a href="../../README.md"><img src="../../GiDo/lang/EN-en-off.svg" height="26" alt="English"></a>
<a href="../../GiDo/RU-ru/README.md"><img src="../../GiDo/lang/RU-ru-off.svg" height="26" alt="Русский"></a>
<a href="../../GiDo/ZH-cn/README.md"><img src="../../GiDo/lang/ZH-cn-off.svg" height="26" alt="简体中文"></a>
<a href="../../GiDo/ES-es/README.md"><img src="../../GiDo/lang/ES-es-off.svg" height="26" alt="Español"></a>
<a href="../../GiDo/HI-in/README.md"><img src="../../GiDo/lang/HI-in-off.svg" height="26" alt="हिन्दी"></a>
<a href="../../GiDo/FR-fr/README.md"><img src="../../GiDo/lang/FR-fr-off.svg" height="26" alt="Français"></a>
<a href="../../GiDo/BN-bd/README.md"><img src="../../GiDo/lang/BN-bd-off.svg" height="26" alt="বাংলা"></a>
<a href="../../GiDo/PT-br/README.md"><img src="../../GiDo/lang/PT-br-on.svg" height="26" alt="Português"></a>
<a href="../../GiDo/UR-pk/README.md"><img src="../../GiDo/lang/UR-pk-off.svg" height="26" alt="اردو"></a>
<a href="../../GiDo/ID-id/README.md"><img src="../../GiDo/lang/ID-id-off.svg" height="26" alt="Indonesia"></a>
<a href="../../GiDo/DE-de/README.md"><img src="../../GiDo/lang/DE-de-off.svg" height="26" alt="Deutsch"></a>
<a href="../../GiDo/JA-jp/README.md"><img src="../../GiDo/lang/JA-jp-off.svg" height="26" alt="日本語"></a>
<a href="../../GiDo/TR-tr/README.md"><img src="../../GiDo/lang/TR-tr-off.svg" height="26" alt="Türkçe"></a>
<a href="../../GiDo/KO-kr/README.md"><img src="../../GiDo/lang/KO-kr-off.svg" height="26" alt="한국어"></a>
<a href="../../GiDo/VI-vn/README.md"><img src="../../GiDo/lang/VI-vn-off.svg" height="26" alt="Tiếng Việt"></a>
<a href="../../GiDo/IT-it/README.md"><img src="../../GiDo/lang/IT-it-off.svg" height="26" alt="Italiano"></a>
<a href="../../GiDo/PL-pl/README.md"><img src="../../GiDo/lang/PL-pl-off.svg" height="26" alt="Polski"></a>
<a href="../../GiDo/UK-ua/README.md"><img src="../../GiDo/lang/UK-ua-off.svg" height="26" alt="Українська"></a>
<a href="../../GiDo/TH-th/README.md"><img src="../../GiDo/lang/TH-th-off.svg" height="26" alt="ไทย"></a>
<a href="../../GiDo/KK-kz/README.md"><img src="../../GiDo/lang/KK-kz-off.svg" height="26" alt="Қазақша"></a>
<a href="../../GiDo/UZ-uz/README.md"><img src="../../GiDo/lang/UZ-uz-off.svg" height="26" alt="Oʻzbekcha"></a>
<a href="../../GiDo/BE-by/README.md"><img src="../../GiDo/lang/BE-by-off.svg" height="26" alt="Беларуская"></a>
<a href="../../GiDo/AZ-az/README.md"><img src="../../GiDo/lang/AZ-az-off.svg" height="26" alt="Azərbaycanca"></a>
<a href="../../GiDo/HY-am/README.md"><img src="../../GiDo/lang/HY-am-off.svg" height="26" alt="Հայերեն"></a>
<a href="../../GiDo/ISV-sl/README.md"><img src="../../GiDo/lang/ISV-sl-off.svg" height="26" alt="Medžuslovjansky"></a>
<a href="../../GiDo/HE-il/README.md"><img src="../../GiDo/lang/HE-il-off.svg" height="26" alt="עברית"></a>
</p>

<p align="center"><a href="https://github.com/Arkomiko/Fruity-Organizer-DataBase/releases/latest"><b>⬇ Baixar FODB.exe</b></a> &nbsp;|&nbsp; <a href="https://arkomiko.github.io/Fruity-Organizer-DataBase/PT-br/wiki/index.html"><b>Wiki</b></a></p>

Um organizador portátil para o banco de plugins do FL Studio. Coloca os plugins em pastas por fabricante, por finalidade ou ambos, com um visual que combina com o FL Studio.

<p align="center"><img src="../../GiDo/demo-en.gif" alt="FODB" width="100%"></p>

## Recursos

- Organize por fabricante, por finalidade ou aninhe em qualquer ordem: Fabricante\Finalidade ou Finalidade\Fabricante
- Identifica para que serve cada plugin: reverb, EQ, dinâmica, sintetizador e mais 18 finalidades
- Filtros por finalidade, fabricante, formato, bits, status, data do arquivo, tamanho e mais
- Acompanha o tema atual do FL Studio em tempo real
- Backups automáticos, desfazer com um clique, nada sai da pasta do banco
- Um único arquivo de 10 MB sem instalação; as configurações ficam ao lado dele
- 26 idiomas de interface e ajustes de organização, atalhos, escala, fontes, cores e mais

## Início rápido

1. Baixe o FODB.exe e execute. O banco de plugins é encontrado automaticamente.
2. Escolha um layout de pastas e ative as fontes e os filtros desejados.
3. Clique em “Organizar plugins”, confira a prévia e atualize o navegador de plugins no FL Studio.

## Layouts de pastas

<p align="center"><img src="workflow.svg" alt="Layouts de pastas" width="100%"></p>

Escolha uma predefinição ou escreva seu modelo com estas partes:

```text
{vendor}  {purpose}  {format}  {bits}  {letter}  {kind}

{vendor}\{purpose}
{purpose}\{vendor}
USER\{format}\{vendor}
```

## Filtros

Marque valores no menu Filtros ou digite condições na caixa de busca:

```text
purpose:reverb,delay                 reverb OR delay
vendor:"plugin alliance" -format:vst  one vendor, without VST2
organized:no kind:synth               synths not organized yet
age:30d bits:64                       64-bit, dated in the last 30 days
```

## Temas do FL Studio

<p align="center"><img src="themes.svg" alt="Temas do FL Studio" width="100%"></p>

O FODB lê o tema ativo e atualiza as cores quando você o troca no FL Studio. As cores base são muito próximas, mas não idênticas pixel a pixel.

## Segurança

- Seus plugins nunca são alterados. Na pasta Installed só a lista New pode mudar: o plugin organizado sai dela, e isso pode ser desativado.
- Cada execução pode ser desfeita, e os arquivos removidos vão para a Lixeira.
- Antes de cada alteração é criado um backup ZIP do banco; os 40 mais recentes são mantidos e o número é ajustável.

## Suas próprias regras

Adicione regras na aba Configurações ou no FODB.json para definir o uso por nome ou fabricante com expressões regulares:

```json
"purpose_rules": [
  { "purpose": "drums", "name": "kick|808" },
  { "purpose": "vocal", "vendor": "antares" }
]
```

## Compilar do código-fonte

Requer Windows e Python 3.13. O programa usa apenas a biblioteca padrão.

```powershell
./packaging/build.ps1
```

## Créditos

Baseado no FL Studio Automatic Plugin Organizer de Magabes e colaboradores, sob licença MIT.

Projeto independente, sem vínculo com a Image-Line. FL Studio é uma marca da Image-Line.
