# Projeto-Fisher

O Sistema de Controle de Custo Alimentar e Biometria de Peixes foi desenvolvido para auxiliar piscicultores no gerenciamento da alimentação dos peixes, reduzindo desperdícios e melhorando o controle da produção.

O sistema permite registrar as biometrias (pesagens amostrais dos peixes), calcular a biomassa total de cada tanque e estimar a quantidade ideal de ração que deve ser fornecida diariamente.

## Recursos

- **Painel central** com o bem-estar geral (%), nível de ração (%), adequação da temperatura (%), alertas e as últimas alterações feitas.
- **Cálculo de ração** por espécie, faixa de peso e temperatura, com a taxa em % do peso vivo, refeições por dia e proteína recomendada (arquivo `racao.py`).
- **Bem-estar de cada tanque** (0 a 100%): temperatura, alimentação e biometria em dia.
- **Estoque de ração** com desconto automático a cada trato e previsão de dias restantes.
- **Tanques**: cadastrar, editar, duplicar, excluir, buscar, filtrar, ordenar e exportar para planilha (CSV).
- **Biometria** com simulador ao vivo, gráficos de crescimento e temperatura, registro de tratos e de mortalidade.
- **Histórico** completo de tudo que foi alterado.

## Como rodar

```
pip install -r requirements.txt
copie .env.example para .env e preencha FISHER_SECRET_KEY e FISHER_DATABASE_URI
python app.py
```

### Administrador

- A primeira conta criada num sistema **sem nenhum administrador** vira administradora automaticamente.
- Para promover uma conta que já existe: `flask --app app promover-admin email@exemplo.com`
- Admin padrão: `flask --app app init-admin` (cria `admin@gmail.com`; troque a senha depois).
- Depois disso, o admin promove/rebaixa pelo menu **Painel Admin**.

### Banco de dados

Ao iniciar, o sistema adiciona sozinho as colunas/tabela novas (se o usuário do `.env` tiver permissão).
Se não tiver, rode uma vez, como administrador do MySQL: `mysql -u fisher_admin -p fisher < banco/migracao_v2.sql`
(isso também remove o trigger antigo de desconto de ração, que agora é feito pela aplicação).

## Ajustando o cálculo

As faixas de temperatura e as taxas de ração de cada espécie ficam na tabela `PERFIS`, no início do arquivo `racao.py`. São referências gerais de manejo: confirme com o seu zootecnista ou técnico antes de adotar.
