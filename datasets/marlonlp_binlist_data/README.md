# Lista BIN (IIN)

Este repositório contém uma lista open-source de Issuer Identification Numbers (IIN), também conhecidos como Bank Identification Numbers (BIN).

Os primeiros 6 dígitos (em alguns casos 6–8) de um cartão de crédito ou débito identificam o emissor (banco ou instituição financeira). Os dados aqui foram compilados a partir de diversas fontes públicas e contribuições da comunidade.

Aviso: estes dados foram coletados por scraping e curadoria manual. Embora a lista seja abrangente, ela não é um registro oficial de IINs. Use por sua conta e risco.

---

## Arquivo de dados

O arquivo principal com os dados chama-se `binlist-data.csv` e está no formato CSV com os seguintes pontos importantes:

- Delimitador: ponto e vírgula (`;`).
- Linha de cabeçalho presente (primeira linha).
- Encoding recomendado: UTF-8.
- Valores desconhecidos/omissos são deixados em branco.

Cabeçalho atual (ordem das colunas):

```
bin;brand;type;category;issuer
```

## Descrição dos campos

Cada linha do arquivo representa um BIN/IIN com metadados. Abaixo uma descrição de cada coluna:

- bin
  - O identificador do BIN/IIN. Normalmente são os primeiros 6 dígitos do número do cartão (formato numérico, zeros à esquerda preservados). Exemplo: `004078`, `100001`.
  - Observação: algumas fontes usam 8 dígitos; aqui os valores são apresentados como 6 dígitos quando aplicável.

- brand
  - A marca ou rede do cartão (por exemplo: `VISA`, `MASTERCARD`, `PRIVATE LABEL`, `PAGOBANCOMAT`, `LOCAL BRAND`, `UATP`).

- type
  - Tipo do produto do cartão: `DEBIT`, `CREDIT`, `PREPAID`, `UATP`, etc.

- category
  - Categoria ou classe do cartão (por exemplo `STANDARD`, `GIFT`, `PLATINUM`, `CLASSIC`, `PROPRIETARY ATM`). Pode estar em branco.

- issuer
  - Nome do emissor (banco ou instituição) quando conhecido. Exemplo: `CHINA MERCHANTS BANK`, `BNI BANK`, `STATE BANK OF INDIA`. Pode estar em branco.

Exemplo de linhas (do arquivo):

```
004078;PRIVATE LABEL;DEBIT;GIFT;SHIFT4 PAYMENTS
100001;LOCAL BRAND;DEBIT;CLASSIC;STATE BANK OF INDIA
002102;PRIVATE LABEL;CREDIT;STANDARD;CHINA MERCHANTS BANK
```

## Como usar

Exemplos rápidos para inspecionar o arquivo.

Com pandas (Python):

```python
import pandas as pd

df = pd.read_csv('binlist-data.csv', sep=';', dtype=str, encoding='utf-8')
print(df.head())
```

PowerShell - mostrar as primeiras linhas:

```powershell
Get-Content .\binlist-data.csv -TotalCount 20
```

PowerShell - filtrar por BIN específico:

```powershell
Select-String -Path .\binlist-data.csv -Pattern '^004078;' -SimpleMatch
```

Dicas ao processar:

- Trate campos em branco como valores desconhecidos.
- Remova espaços em excesso nas colunas (trim) antes de comparações.
- Normalizar case (uppercase/lowercase) pode ajudar em buscas consistentes.

## Contribuindo

Contribuições são bem-vindas. Fluxo recomendado:

1. Faça fork do repositório no GitHub.
2. Edite `binlist-data.csv` respeitando o formato `bin;brand;type;category;issuer`.
3. Na mensagem do commit, cite a fonte/URL da informação quando possível.
4. Abra um Pull Request com descrição clara das alterações.

Evite remover histórico sem motivo e mantenha a formatação do arquivo.

## Licença

O conteúdo deste repositório está licenciado sob a licença Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/.

## Observações finais

Esta lista foi mantida com fins educacionais e utilitários pela comunidade. Não é um registro oficial de BIN/IINs. Se você usar os dados em produção, verifique com fontes oficiais quando necessário.

Dúvidas, problemas ou pedidos de atualização podem ser abertos como Issues no repositório do GitHub.
# Lista BIN (IIN)

Este repositório contém uma lista open-source de Issuer Identification Numbers (IIN), também conhecidos como Bank Identification Numbers (BIN).

Os primeiros 6 dígitos (em alguns casos 6–8) de um cartão de crédito ou débito identificam o emissor (banco ou instituição financeira). Os dados aqui foram compilados a partir de diversas fontes públicas e contribuições da comunidade.

Aviso: estes dados foram coletados por scraping e curadoria manual. Embora a lista seja abrangente, ela não é um registro oficial de IINs. Use por sua conta e risco.

## Arquivo de dados

O arquivo principal com os dados chama-se `binlist-data.csv` e está no formato CSV com os seguintes pontos importantes:

- Delimitador: ponto e vírgula (`;`).
- Linha de cabeçalho presente (primeira linha).
- Encoding recomendado: UTF-8.
- Valores desconhecidos/omissos são deixados em branco.

Cabeçalho atual (ordem das colunas):

```
bin;brand;type;category;issuer
```

## Descrição dos campos

Cada linha do arquivo representa um BIN/IIN com metadados. Abaixo uma descrição de cada coluna:

- bin
  - O identificador do BIN/IIN. Normalmente são os primeiros 6 dígitos do número do cartão (formato numérico, zeros à esquerda preservados). Exemplo: `004078`, `100001`.
  - Observação: algumas fontes usam 8 dígitos; aqui os valores são apresentados como 6 dígitos quando aplicável.

- brand
  - A marca ou rede do cartão (por exemplo: `VISA`, `MASTERCARD`, `PRIVATE LABEL`, `PAGOBANCOMAT`, `LOCAL BRAND`, `UATP`).

- type
  - Tipo do produto do cartão: `DEBIT`, `CREDIT`, `PREPAID`, `UATP`, etc.

- category
  - Categoria ou classe do cartão (por exemplo `STANDARD`, `GIFT`, `PLATINUM`, `CLASSIC`, `PROPRIETARY ATM`). Pode estar em branco.

- issuer
  - Nome do emissor (banco ou instituição) quando conhecido. Exemplo: `CHINA MERCHANTS BANK`, `BNI BANK`, `STATE BANK OF INDIA`. Pode estar em branco.

Exemplo de linhas (do arquivo):

```
004078;PRIVATE LABEL;DEBIT;GIFT;SHIFT4 PAYMENTS
100001;LOCAL BRAND;DEBIT;CLASSIC;STATE BANK OF INDIA
002102;PRIVATE LABEL;CREDIT;STANDARD;CHINA MERCHANTS BANK
```

## Como usar

Exemplos rápidos para inspecionar o arquivo.

Com pandas (Python):

```python
import pandas as pd

df = pd.read_csv('binlist-data.csv', sep=';', dtype=str, encoding='utf-8')
print(df.head())
```

PowerShell - mostrar as primeiras linhas:

```powershell
Get-Content .\binlist-data.csv -TotalCount 20
```

PowerShell - filtrar por BIN específico:

```powershell
Select-String -Path .\binlist-data.csv -Pattern '^004078;' -SimpleMatch
```

Dicas ao processar:

- Trate campos em branco como valores desconhecidos.
- Remova espaços em excesso nas colunas (trim) antes de comparações.
- Normalizar case (uppercase/lowercase) pode ajudar em buscas consistentes.

## Contribuindo

Contribuições são bem-vindas. Fluxo recomendado:

1. Faça fork do repositório no GitHub.
2. Edite `binlist-data.csv` respeitando o formato `bin;brand;type;category;issuer`.
3. Na mensagem do commit, cite a fonte/URL da informação quando possível.
4. Abra um Pull Request com descrição clara das alterações.

Evite remover histórico sem motivo e mantenha o formatação do arquivo.

## Licença

O conteúdo deste repositório está licenciado sob a licença Creative Commons Attribution 4.0 International (CC BY 4.0): https://creativecommons.org/licenses/by/4.0/.

## Observações finais

Esta lista foi mantida com fins educacionais e utilitários pela comunidade. Não é um registro oficial de BIN/IINs. Se você usar os dados em produção, verifique com fontes oficiais quando necessário.

Dúvidas, problemas ou pedidos de atualização podem ser abertos como Issues no repositório do GitHub.

# Lista BIN (IIN) — open-source

Este repositório contém uma lista open-source de Issuer Identification Numbers (IIN), também conhecidos como Bank Identification Numbers (BIN).

Os primeiros 6 dígitos (em alguns casos 6–8) de um cartão de crédito ou débito identificam o emissor (banco ou instituição financeira). Os dados aqui foram compilados a partir de diversas fontes públicas e contribuições da comunidade.

Aviso: estes dados foram coletados por scraping e curadoria manual. Embora a lista seja abrangente, ela não é um registro oficial de IIN/IINs. Use por sua conta e risco.

## Arquivo de dados

O arquivo principal com os dados chama-se `binlist-data.csv` e está no formato CSV com os seguintes pontos importantes:

- Delimitador: ponto e vírgula (`;`).
- Linha de cabeçalho presente (primeira linha).
- Encoding esperado: UTF-8 (pode variar dependendo do editor).
- Valores desconhecidos/omissos são deixados em branco.

Cabeçalho atual (ordem das colunas):

```
bin;brand;type;category;issuer
```

## Descrição dos campos

Cada linha do arquivo representa um BIN/IIN com metadados. Abaixo uma descrição de cada coluna:

- bin
  - O identificador do BIN/IIN. Normalmente são os primeiros 6 dígitos do número do cartão (formato numérico, zero à esquerda preservado). Exemplo: `004078`, `100001`.
  - Observação: em algumas fontes podem aparecer IINs com mais de 6 dígitos; neste arquivo os valores apresentados usam 6 dígitos.

- brand
  - A marca ou rede do cartão (por exemplo: `VISA`, `MASTERCARD`, `PRIVATE LABEL`, `PAGOBANCOMAT`, `LOCAL BRAND`, `UATP`, etc.).
  - Indica a rede ou rótulo comercial associado ao BIN.

- type
  - Tipo do produto do cartão, por exemplo `DEBIT`, `CREDIT`, `PREPAID`, `UATP`.
  - Campo útil para filtrar transações por tipo de cartão.

- category
  - Categoria ou classe do cartão (por exemplo `STANDARD`, `GIFT`, `PLATINUM`, `CLASSIC`, `PROPRIETARY ATM`, `UATP`, etc.).
  - Pode estar em branco quando não houver informação conhecida.

- issuer
  - Nome do emissor (banco ou instituição) quando conhecido. Exemplo: `CHINA MERCHANTS BANK`, `BNI BANK`, `STATE BANK OF INDIA`, `SHIFT4 PAYMENTS`.
  - Também pode estar em branco se o emissor não foi identificado.

Exemplo de linhas (do arquivo):

```
004078;PRIVATE LABEL;DEBIT;GIFT;SHIFT4 PAYMENTS
100001;LOCAL BRAND;DEBIT;CLASSIC;STATE BANK OF INDIA
002102;PRIVATE LABEL;CREDIT;STANDARD;CHINA MERCHANTS BANK
```

## Como usar

Exemplos rápidos para inspecionar o arquivo.

Com pandas (Python):

```python
import pandas as pd

df = pd.read_csv('binlist-data.csv', sep=';', dtype=str, encoding='utf-8')
print(df.head())
```

Linha de comando (PowerShell) - mostrar as primeiras linhas:

```powershell
Get-Content .\binlist-data.csv -TotalCount 20
```

Filtrar por BIN específico (PowerShell):

```powershell
Select-String -Path .\binlist-data.csv -Pattern '^004078;' -SimpleMatch
```

Observações ao processar:
- Trate campos em branco (empty strings) como valores desconhecidos.
- Remova espaços em excesso nas colunas se necessário (trim).
- Alguns registros podem usar letras maiúsculas (uppercase) — normalizar se precisar fazer comparações.

## Contribuindo

Contribuições são bem-vindas. Recomenda-se seguir este fluxo:

1. Fork do repositório no GitHub.
2. Edite `binlist-data.csv` adicionando ou corrigindo linhas no mesmo formato: `bin;brand;type;category;issuer`.
3. Inclua na mensagem do commit a fonte/URL da informação (quando possível) — isso facilita a validação.
4. Abra um Pull Request com uma descrição clara das alterações.

Por favor, evite remover histórico existente sem motivo e mantenha o formato do arquivo.

## Licença

O conteúdo deste repositório está licenciado sob a licença Creative Commons Attribution 4.0 International (CC BY 4.0). Para mais detalhes consulte: https://creativecommons.org/licenses/by/4.0/.

## Observações finais

Esta lista foi mantida com fins educacionais e utilitários pela comunidade. Não é um registro oficial de BIN/IINs. Se você usar os dados em produção, verifique com fontes oficiais quando necessário.

Problemas, dúvidas e pedidos de atualização podem ser abertos como Issues no repositório do GitHub.
