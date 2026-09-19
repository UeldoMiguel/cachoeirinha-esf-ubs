# Mapa Territorial da Saúde — Cachoeirinha/RS

Aplicação web estática que mostra, sobre o mapa de Cachoeirinha/RS, a divisão territorial das áreas de **ESF** (Estratégia Saúde da Família) e **UBS** (Unidades Básicas de Saúde), a localização das unidades de saúde e qual unidade atende cada território.

**Publicação:** https://ueldomiguel.github.io/cachoeirinha-esf-ubs/

Duas páginas compõem o projeto:

| Página | Para quê |
|---|---|
| [`index.html`](index.html) | Aplicação principal: mapa com camadas, legenda, popups, **consulta por endereço** e **modo escuro**. Lê os GeoJSON de `data/`. |
| [`consulta/index.html`](consulta/index.html) | A mesma consulta por endereço em página própria, arquivo único com os dados embutidos. Fica de pé para quem precisa do arquivo offline ou de um link direto só da consulta. |

> **Aviso sobre os dados.** Os limites territoriais aqui publicados foram digitalizados de mapa colaborativo público e servem como dado de trabalho. **Não substituem o cadastro oficial** da Secretaria Municipal de Saúde de Cachoeirinha. Os limites oficiais devem ser fornecidos pela fonte responsável e substituídos nos arquivos de `data/` (veja abaixo) — a aplicação não precisa de nenhuma alteração para passar a usá-los.

## 1. Objetivo

Dar a gestores, equipes e à população uma forma direta de responder a duas perguntas:

1. **Qual é o território de cada unidade?** — polígonos de ESF e UBS desenhados sobre o mapa, com legenda e controle de camadas.
2. **Qual unidade atende este endereço?** — busca por nome de unidade/área no mapa, e busca por rua e número na página de consulta.

## 1.1 O que a página faz

- **Camadas** de áreas de ESF, áreas de UBS, unidades e limite municipal, com liga/desliga e contagem.
- **Consulta por endereço** na mesma caixa de busca: digitar "Rua Dom Bosco, 240" responde se o endereço é área de ESF ou de UBS, mostra a unidade de referência com telefone e desenha a via em vermelho sobre o mapa. Com o número da casa, o vermelho cobre **só o lado de quadra daquela numeração** (faces de quadra do CNEFE 2022). Em rua de divisa, o número decide a unidade.
- A mesma caixa também acha **unidades e áreas pelo nome**.
- **Modo escuro**, com botão no topo. Sem escolha manual a página acompanha o sistema; a escolha fica gravada no navegador. Os tiles do OSM são invertidos por CSS — nenhum serviço de base escura com chave de API foi introduzido.
- **Popup e painel** mostram apenas: nome, unidade de referência, tipo, endereço, telefone e e-mail. Campo que a fonte não traz não aparece.
- **Áreas e ruas recortadas no limite municipal**: os polígonos do mapa colaborativo passavam da divisa (o da UBS Parque da Matriz avançava 26% para fora) e a malha viária também. Os dois são cortados pelo limite do OpenStreetMap na geração dos dados.

## 2. Tecnologias

- HTML, CSS e JavaScript puros, sem framework e sem etapa de build para publicar.
- [Leaflet 1.9.4](https://leafletjs.com/) via CDN (unpkg), com camada-base do OpenStreetMap.
- GeoJSON (RFC 7946) como formato de dados.
- GitHub Pages para hospedagem.
- Python 3 (biblioteca padrão) apenas para *regerar* os dados — não é necessário para usar ou publicar o site.

## 3. Estrutura dos arquivos

```
cachoeirinha-esf-ubs/
├── index.html              aplicação do mapa
├── css/style.css           estilos (tokens de cor no :root)
├── js/map.js               carga dos GeoJSON, camadas, popups, busca
├── js/consulta.js          consulta por endereço (rua, número, trecho de quadra)
├── js/tema.js              modo claro/escuro
├── data/                   dados publicados, consumidos pelo navegador
│   ├── esf.geojson         polígonos das áreas de ESF
│   ├── ubs.geojson         polígonos das áreas de UBS
│   ├── unidades.geojson    pontos das unidades e serviços
│   ├── limite.geojson      contorno do município (OpenStreetMap)
│   ├── consulta.json       índice de ruas, traçados e numeração (consulta)
│   └── metadados.json      procedência, data de geração e contagens
├── assets/favicon.svg
├── consulta/index.html     página de consulta por endereço (arquivo único)
├── scripts/                geração dos dados (Python) — não roda no navegador
├── dados/                  fontes e intermediários do processamento
├── dist/artifact.html      variante da consulta para publicação como Artifact
├── ruas-nao-contempladas.csv
├── .nojekyll               evita o processamento Jekyll no GitHub Pages
├── LICENSE                 MIT para o código; licenças dos dados descritas nele
└── README.md
```

Todos os caminhos no HTML, CSS e JS são **relativos** (`css/style.css`, `data/esf.geojson`), como exige a publicação em subdiretório do `github.io`.

## 4. Como adicionar ou substituir arquivos GeoJSON

A troca de dados é feita **sem tocar no código**:

1. Coloque o arquivo em `data/` com um dos nomes já usados (`esf.geojson`, `ubs.geojson`, `unidades.geojson`, `limite.geojson`) para substituir uma camada existente.
2. Para acrescentar uma camada nova, adicione o arquivo em `data/` e uma linha na lista `FONTES`, no começo de [`js/map.js`](js/map.js):

```javascript
var FONTES = [
  { id: 'esf',  arquivo: 'data/esf.geojson',  rotulo: 'Áreas de ESF', especie: 'area', tipo: 'ESF' },
  { id: 'ubs',  arquivo: 'data/ubs.geojson',  rotulo: 'Áreas de UBS', especie: 'area', tipo: 'UBS' },
  { id: 'unidades', arquivo: 'data/unidades.geojson', rotulo: 'Unidades de saúde', especie: 'ponto' },
  { id: 'limite',   arquivo: 'data/limite.geojson',   rotulo: 'Limite do município', especie: 'limite' }
  // nova camada:
  // { id: 'microareas', arquivo: 'data/microareas.geojson', rotulo: 'Microáreas', especie: 'area', tipo: 'ESF' }
];
```

`especie` aceita `area` (polígonos clicáveis, com destaque no hover), `ponto` (marcadores) e `limite` (linha de contorno, não clicável). A camada nova ganha automaticamente caixa no controle de camadas, entrada na busca e popup.

3. Faça commit e envie: o GitHub Pages republica sozinho em cerca de um minuto.

**Coordenadas em EPSG:4326** (longitude, latitude), como manda a RFC 7946. Se o dado oficial vier em SIRGAS 2000 / UTM, converta antes (QGIS: *Exportar → Salvar feições como… → GeoJSON → SRC EPSG:4326*).

## 5. Estrutura esperada dos GeoJSON

Propriedades genéricas; **o que não existir é simplesmente omitido** — a aplicação nunca preenche campo ausente:

```json
{
  "type": "Feature",
  "properties": {
    "nome": "Área da ESF Canarinho",
    "unidade": "ESF Canarinho",
    "tipo": "ESF",
    "codigo": "ESF-CANARINHO",
    "descricao": "Território de abrangência da ESF Canarinho",
    "equipe": "Equipe 3",
    "territorio": "Canarinho / Vila Anair",
    "telefone": "(51) 3041-0000",
    "email": "esf.canarinho@cachoeirinha.rs.gov.br",
    "ruas": ["Rua A", "Rua B"]
  },
  "geometry": { "type": "Polygon", "coordinates": [[[-51.09, -29.95], [-51.08, -29.95], [-51.08, -29.94], [-51.09, -29.95]]] }
}
```

- `tipo` controla a cor: `ESF` (verde), `UBS` (azul), qualquer outro valor cai na cor de "outros serviços".
- A caixa de informações mostra **apenas** `nome`, `unidade`, `tipo`, `telefone` e `email`. As demais propriedades ficam no arquivo (e servem ao processamento), mas fora da interface. Para exibir outra, acrescente uma linha ao array `CAMPOS` no topo de [`js/map.js`](js/map.js).
- `codigo` é a chave que liga uma rua ao polígono na consulta por endereço: ao trocar os GeoJSON, mantenha os mesmos códigos ou regenere `data/consulta.json`.

## 6. Como adicionar novas unidades

Acrescente uma feição de ponto em `data/unidades.geojson`:

```json
{
  "type": "Feature",
  "properties": {
    "nome": "ESF Nome da Unidade",
    "tipo": "ESF",
    "codigo": "ESF-NOME-DA-UNIDADE",
    "endereco": "Rua Exemplo, 100 — Bairro",
    "telefone": "(51) 3041-0000",
    "equipe": "Equipe 1",
    "territorio": "Nome do território"
  },
  "geometry": { "type": "Point", "coordinates": [-51.0939, -29.9509] }
}
```

Atenção à ordem **[longitude, latitude]**. Sem coordenada real da unidade, não crie a feição: é preferível a unidade não aparecer no mapa a aparecer no lugar errado.

## 7. Como executar localmente

O navegador bloqueia `fetch` de arquivos abertos por `file://`, então use um servidor local:

```bash
python -m http.server 8000
```

Depois abra `http://localhost:8000/`. A página `consulta/index.html` é autocontida e abre com duplo clique, sem servidor.

Para regerar os dados (só é preciso quando as fontes mudam):

```bash
cd dados && python ../scripts/fetch_osm.py && python ../scripts/cnefe.py && python ../scripts/parse.py && python ../scripts/lines_osm.py && python ../scripts/build.py && python ../scripts/enderecos.py && python ../scripts/oficial.py && python ../scripts/final.py
```

e, da raiz:

```bash
python scripts/geojson.py && python scripts/consulta_dados.py && python scripts/build_html.py
```

`scripts/geojson.py` gera os GeoJSON de `data/`; `scripts/consulta_dados.py` gera `data/consulta.json`; `scripts/build_html.py` gera `consulta/index.html`.

## 8. Como publicar no GitHub Pages

1. **Settings → Pages**.
2. **Source:** *Deploy from a branch*.
3. **Branch:** `main`, pasta `/ (root)`. Salvar.
4. Em um a dois minutos o site fica em `https://ueldomiguel.github.io/cachoeirinha-esf-ubs/`.

O arquivo `.nojekyll` na raiz desliga o processamento Jekyll, que não é necessário aqui.

## 8.1 Recorte no limite municipal e endereços

`scripts/final.py` monta o polígono do município a partir do limite do OpenStreetMap (44,1 km², o mesmo valor do IBGE) e o usa para recortar as áreas de abrangência que passavam da divisa — a da UBS Parque da Matriz perdeu 26%, a da ESF Carlos Wilkens 2% — e a malha viária desenhada, que atravessava para Gravataí e Canoas. Cada rua do índice é conferida contra esse polígono: só sai quando nenhum pedaço dela cai dentro do município. Depende de [Shapely](https://shapely.readthedocs.io/) (`pip install shapely`), usado apenas na geração dos dados.

**Telefone e endereço vêm da lista de contatos da Secretaria Municipal de Saúde**, transcrita em `dados/unidades_oficiais.json` — fonte oficial, com precedência sobre qualquer dado deduzido. `scripts/oficial.py` geocodifica cada endereço pelo CNEFE e compara com o ponto do mapa colaborativo; `scripts/geojson.py` grava esses contatos nas feições. Três unidades da lista não existiam no mapa — **eMulti, SAE - Tuberculose e SAM** — e entraram posicionadas pela coordenada do próprio endereço.

`scripts/enderecos.py` atende às duas unidades fora da lista (Secretaria de Saúde e Hospital Padre Jeremias): casa a unidade com o estabelecimento de saúde correspondente no CNEFE 2022 (espécie 5), por nome ou por proximidade de até 80 m. A grafia com acento vem dos nomes de via do OpenStreetMap, já que o CNEFE guarda tudo sem acento.

## 9. Dados territoriais oficiais

Os polígonos e as listas de ruas atualmente publicados vêm de mapa colaborativo público e são **dados de trabalho**. Os limites oficiais das áreas de abrangência, a lotação das equipes e o cadastro das unidades devem ser fornecidos pela **Secretaria Municipal de Saúde de Cachoeirinha**. Quando forem disponibilizados, substitua os arquivos de `data/` conforme a seção 4 — a aplicação passa a exibi-los sem nenhuma alteração de código.

Fontes usadas hoje:

- Áreas, unidades e listas de ruas: mapa colaborativo "Mapeamento unidades de saúde — Cachoeirinha" (Google My Maps).
- Malha viária e limite municipal: OpenStreetMap, contribuidores (ODbL).
- Telefone e endereço das unidades: lista de contatos da Secretaria Municipal de Saúde de Cachoeirinha/RS.
- Numeração de endereços, faces de quadra e geocodificação: CNEFE 2022, IBGE, município 4303103.

## 10. Licença

Código sob **MIT** (veja [LICENSE](LICENSE)). Os dados seguem as licenças das respectivas fontes, descritas no mesmo arquivo.
