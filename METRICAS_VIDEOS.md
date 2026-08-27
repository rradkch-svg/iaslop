# 📊 Registro de Métricas e Feedback Analítico — Minuto Inexplicável

Utilize este arquivo ou o arquivo `METRICAS_VIDEOS.csv` para registrar as métricas reais fornecidas pelo **YouTube Studio** após a publicação dos Shorts.
Após editar este arquivo, execute `python scripts/sync_metrics.py` para calibrar automaticamente a memória algorítmica da IA.

---

## 📋 Tabela de Vídeos Publicados e Métricas Reais

| Batch / Vídeo | Título do Mistério | Visualizações | Retenção 3s (%) | APV % (Média Vista) | CTR % | Likes | Comentários | Observações / Desempenho |
| :--- | :--- | :---: | :---: | :---: | :---: | :---: | :---: | :--- |
| `batch_0/video_0` | A Base Nuclear Secreta Enterrada Sob o Gelo | 48.500 | 82,4% | 89,1% | 12,5% | 3.200 | 410 | Excelente retenção no gancho do reator polar |
| `batch_0/video_1` | O Poço Mais Fundo da Terra e os Sons de Kola | 62.000 | 85,1% | 91,3% | 14,2% | 4.500 | 620 | Pico de comentários sobre anomalia térmica |
| `batch_0/video_2` | O Enigma do Passo Dyatlov nos Montes Urais | 55.000 | 79,8% | 87,4% | 11,8% | 3.800 | 530 | Debate intenso sobre teorias científicas |
| `batch_0/video_3` | Derinkuyu: A Cidade Subterrânea de 18 Andares | 41.200 | 77,5% | 84,2% | 10,5% | 2.900 | 340 | Curiosidade alta nos 18 andares de pedra |

---

## 💡 Como Sincronizar com a IA

1. Insira novas linhas na tabela acima ou no arquivo `METRICAS_VIDEOS.csv`.
2. No terminal, execute:
   ```bash
   python scripts/sync_metrics.py
   ```
3. A IA atualizará os pesos em `data/algorithm_memory/ALGORITHM_MEMORY.md` e usará os ganchos e ritmos de maior sucesso nos próximos batches!
