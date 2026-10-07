# Brisa · Weather App

Aplicação FastAPI + JavaScript modular + SQLite + Gemini para planejar o dia. Interface em português, responsiva, sem build de frontend e sem dependências de CDN.

### Previsão hora a hora

Selecione **Hoje**, **Amanhã** ou outro card para abrir a previsão horária desse dia. A faixa horizontal mostra horário, condição, temperatura, chance de precipitação e volume previsto. No celular, deslize; no desktop, use a barra ou os botões de seta. Hoje abre na hora atual da cidade, mantendo os horários anteriores disponíveis. A seleção de dias usa os dados já carregados, sem novas chamadas à IA.

O destaque resume o maior percentual e os horários correspondentes (para hoje, considera a hora atual em diante). Valores ausentes aparecem como `—`, nunca como zero. Horários são locais da cidade, independentemente do fuso do dispositivo. Conforme a [definição do Open-Meteo](https://open-meteo.com/en/docs), precipitação e probabilidade são relativas à hora anterior ao horário indicado: por exemplo, o valor das 15:00 corresponde ao intervalo 14:00–15:00. Temperatura e condição correspondem ao horário indicado. A interface explica essa diferença; a previsão não garante o momento exato de início ou fim da chuva.

## Executar

Requer Python 3.11+ e acesso à internet para as APIs. Execute os comandos **dentro da pasta `weather-app`**.

### Windows / PowerShell

```powershell
python -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
Copy-Item .env.example .env
# Edite .env para configurar GEMINI_API_KEY (opcional para iniciar).
.\.venv\Scripts\python.exe -m app.main
```

### Linux / macOS

```bash
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
cp .env.example .env
# Edite .env.
.venv/bin/python -m app.main
```

Abra <http://127.0.0.1:8000>. A página consulta São Paulo inicialmente, com dados reais. Busque outra cidade, escolha um resultado ou use **Minha localização**. A geolocalização depende de permissão do navegador e HTTPS (localhost é permitido). Documentação interativa: <http://127.0.0.1:8000/docs>. Saúde do serviço e banco: `/health`.

`python -m app.main` respeita `HOST` e `PORT` do `.env`. Para desenvolvimento com recarga:

```powershell
.\.venv\Scripts\python.exe -m uvicorn app.main:app --reload --port 8000
```

Ao chamar Uvicorn diretamente, passe host/porta pelos argumentos da CLI.

## Chave do Gemini

1. Entre no [Google AI Studio](https://aistudio.google.com/apikey) com sua conta Google.
2. Crie ou selecione um projeto e crie uma chave na área de API Keys. Se necessário, importe seu projeto existente.
3. Coloque a chave somente no `.env`: `GEMINI_API_KEY=sua_chave`.
4. Reinicie o servidor. Consulte as permissões e quotas do projeto se a interface continuar mostrando **DICA LOCAL · SEM IA**.

O backend usa `from google import genai`, `genai.Client(api_key=...)` e a chamada assíncrona `client.aio.models.generate_content`, com `gemini-2.5-flash` como modelo padrão. O modelo é configurável no `.env` caso sua disponibilidade mude. Consulte a [documentação oficial do SDK](https://googleapis.github.io/python-genai/) e as [instruções oficiais de chaves](https://ai.google.dev/gemini-api/docs/api-key).

Sem chave, em caso de quota, bloqueio, resposta vazia ou timeout de 12 segundos, o backend gera uma dica determinística baseada no clima. Essa dica é identificada como local. A chave nunca é enviada ao navegador. Dados meteorológicos agregados de hoje são enviados ao Gemini; favoritos e histórico não são enviados.

## Estrutura

```text
weather-app/
├── app/
│   ├── __init__.py
│   ├── main.py
│   ├── config.py
│   ├── database.py
│   ├── models.py
│   ├── schemas.py
│   ├── services/
│   │   ├── __init__.py
│   │   ├── weather_service.py
│   │   ├── gemini_service.py
│   │   └── db_service.py
│   └── routes/
│       ├── __init__.py
│       ├── weather.py
│       └── favorites.py
├── static/
│   ├── css/style.css
│   ├── js/api.js
│   ├── js/app.js
│   ├── js/hourly.js
│   └── favicon.svg
├── templates/index.html
├── tests/test_app.py
├── tests/test_hourly.mjs
├── .env.example
├── .gitignore
├── pytest.ini
├── requirements.txt
├── requirements-dev.txt
└── README.md
```

`weather_app.db` é criado automaticamente na raiz do projeto. O SQLAlchemy utiliza `aiosqlite`, sessões por requisição e WAL. O banco contém `favorites` e `search_history`, conforme o esquema solicitado. Favoritos são únicos pelas coordenadas arredondadas a quatro casas decimais. Timestamps são gravados em UTC; SQLite armazena os valores sem o sufixo de fuso. O frontend interpreta esses timestamps como UTC.

## API

| Método e rota | Comportamento |
| --- | --- |
| `GET /api/v1/search?q=Campinas` | Até 5 resultados com `city_name`, `state`, `country`, `lat`, `lon`. Mínimo de 2 caracteres. |
| `GET /api/v1/weather?lat=-23.5505&lon=-46.6333` | Clima atual, hoje, cinco dias seguintes e insight. |
| `GET /api/v1/favorites` | Todos os favoritos. |
| `POST /api/v1/favorites` | Salva cidade; retorna 200 com favorito criado ou existente. |
| `DELETE /api/v1/favorites/{id}` | Retorna 204; 404 se não existir. |
| `GET /api/v1/history` | Dez consultas concluídas mais recentes, em ordem decrescente. |

Exemplo de corpo de favorito:

```json
{"city_name":"Campinas","state":"São Paulo","country":"Brasil","lat":-22.9056,"lon":-47.0608}
```

O endpoint de clima aceita ainda `city_name`, `state`, `country` e `query` opcionais para registrar o termo original e a cidade selecionada. Esses rótulos são metadados fornecidos pelo cliente, não uma geocodificação reversa validada. Sem eles, o histórico registra coordenadas. São registradas consultas de clima concluídas, inclusive hits de cache; digitações do autocomplete e consultas meteorológicas com falha não criam entradas. O clique no histórico repete a busca para desambiguação, pois o esquema solicitado não armazena coordenadas; coordenadas explícitas podem ser reabertas diretamente.

Contrato da resposta meteorológica:

```text
weather_data:
  latitude, longitude, timezone, fetched_at, units
  current: time, temperature, feels_like, humidity, wind_speed,
           precipitation, weather_code, is_day
  today: date, weather_code, temp_max, temp_min,
         precipitation_probability, precipitation_sum, sunrise, sunset
  forecast: [mesmo formato de today, exatamente 5 dias a partir de amanhã]
  hourly: [{time, temperature, precipitation_probability, precipitation, weather_code, is_day}]
ai_insight: texto
ai_source: "gemini" ou "fallback"
cached: true ou false
```

Unidades: °C, km/h, mm e %. A precipitação atual é a fornecida no intervalo atual do provedor. A probabilidade dos cards é a máxima diária, não uma promessa de chuva. O horário do clima e do sol pertence ao fuso da cidade. Nas regiões polares, nascer/pôr do sol ausentes aparecem como `—`. Consulte a [API meteorológica](https://open-meteo.com/en/docs) e a [geocodificação](https://open-meteo.com/en/docs/geocoding-api).

## Cache e falhas

- Cache em memória de 900 segundos, limitado a 512 coordenadas; armazena clima e insight juntos. Há um cache separado para autocomplete, com o mesmo TTL.
- Coordenadas são arredondadas a quatro casas para a chave. Locks assíncronos em 64 faixas deduplicam chamadas concorrentes para a mesma chave. Chaves que compartilham uma faixa aguardam a mesma fila.
- `cached` é calculado por resposta. Dicas locais também ficam no cache pelo TTL; após restaurar a chave/quota, aguarde a expiração ou reinicie o processo.
- Falhas de HTTP, respostas malformadas e dados obrigatórios ausentes do provedor retornam 502 e não são cacheados. Coordenadas inválidas retornam 422.
- O frontend cancela requisições substituídas e ignora resultados atrasados, apresenta skeletons, mensagens de erro e ação para tentar novamente.

## Testes

```powershell
.\.venv\Scripts\python.exe -m pip install -r requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest -q
```

Os testes não consomem quotas externas: usam respostas controladas. Cobrem validação, previsão de cinco dias, histórico, persistência de favoritos, duplicatas, cache/expiração/concorrência, erros do provedor e sucesso/falha/timeout do Gemini. Para validar o Gemini real, configure sua chave e confirme `ai_source: "gemini"` em uma consulta sem cache.

Também cobrem os seis dias de dados horários e a preservação do clima diário se essa série estiver indisponível. Para testar o agrupamento por dia e o resumo de chuva do frontend, use Node.js 22+ (opcional, necessário apenas para esses testes): `node --test --test-isolation=none tests/test_hourly.mjs`.

## Operação e publicação

Este projeto implementa o escopo **de uma instância compartilhada**, sem contas de usuário: todos os visitantes dessa instância veem e alteram os mesmos favoritos e histórico. Não representa um SaaS multitenant com autenticação, cobrança ou isolamento por usuário. Para um serviço público com dados pessoais, adicione identidade e vínculo dos registros ao usuário antes de abrir acesso.

Para uma implantação privada: execute em um servidor com volume persistente para SQLite, backups consistentes pelo mecanismo de backup do SQLite, supervisão do processo e proxy HTTPS. Configure `TRUSTED_HOSTS` com o domínio real e mantenha frontend/API na mesma origem. CORS é fechado por padrão; autorize somente origens específicas se separar o frontend. O proxy deve limitar a taxa de requisições e proteger o acesso à instância e às quotas da IA. Não use `--reload` em produção. Uma execução típica é `uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 1` atrás do proxy.

O cache é local ao processo e se perde ao reiniciar. Use um worker para compartilhar esse cache; para múltiplas réplicas, substitua-o por Redis e reavalie o SQLite. Mudanças futuras no esquema exigem migrações, pois `create_all` apenas cria tabelas ausentes. Fixe as versões resolvidas após validar seu ambiente (`pip freeze > requirements.lock.txt`) para uma implantação reproduzível.

A API gratuita Open-Meteo é destinada a uso não comercial. Para uso comercial, configure o plano adequado, a chave `OPEN_METEO_API_KEY` e as URLs de cliente em `FORECAST_URL`/`GEOCODING_URL`, conforme a [página oficial de planos e limites](https://open-meteo.com/en/pricing). Atribuições de Open-Meteo e GeoNames estão no rodapé.
