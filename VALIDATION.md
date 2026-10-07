# Validação realizada

Data: 6 de outubro de 2026.

- Python 3.12: **18 testes passaram**. Houve um aviso de depreciação da dependência Starlette referente ao transporte HTTPX do TestClient; não houve falhas.
- Node.js: **3 testes passaram**, cobrindo separação de dias no fuso local da cidade, pico de precipitação sem incluir horas passadas e valores ausentes distintos de zero.
- Previsão horária: consulta real com 24 horários por dia; seleção entre hoje e amanhã atualiza temperatura, condição, probabilidade e volume. Dados dos seis dias são retornados junto com a consulta meteorológica.
- Integração real com Open-Meteo: consulta meteorológica de São Paulo e Campinas, geocodificação com cinco resultados, previsão com cinco dias seguintes e hit de cache confirmados.
- Interface no navegador: pesquisa de Campinas com seleção pelo teclado, gravação de favorito, persistência após recarregar, abertura pelo favorito e remoção confirmadas.
- Layout inspecionado em desktop (1440 px) e celular (390 px). Corrigido transbordamento horizontal; a previsão móvel permanece em um carrossel horizontal próprio.
- Módulos JavaScript passaram na verificação de sintaxe; o navegador não registrou erros de JavaScript durante os fluxos verificados.
- Chamada real ao Gemini **não verificada**, pois não foi fornecida uma chave. Sucesso, falha, resposta vazia e timeout foram testados com cliente simulado. O fallback local foi verificado com dados meteorológicos reais.
- Não houve publicação em servidor externo nem teste de carga. Os limites de uma instância compartilhada e os requisitos operacionais estão no README.

As prévias visuais entregues ao lado do ZIP registram os dados reais recebidos no momento da revisão; não são dados fixos do aplicativo. O banco usado na revisão ficou em uma pasta temporária e não integra o pacote.
