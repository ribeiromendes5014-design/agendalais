# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import io
import pytz
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from github import Github, UnknownObjectException

# --- Configurações Essenciais ---
CALENDAR_ID = "manicurelais96@gmail.com"
ARQUIVO_AGENDAMENTOS_CSV = "agendamentos_manicure.csv"
TIMEZONE = 'America/Sao_Paulo'
SCOPES = ['https://www.googleapis.com/auth/calendar']
DURACAO_PADRAO_MIN = 60 # Duração padrão para todos os serviços

# --- Configuração do Fundo (Link direto da imagem) ---
BACKGROUND_IMAGE_URL = "https://i.ibb.co/rK42GP6m/background.jpg"

def set_background(image_url):
    st.markdown(
        f"""
        <style>
        /* --- Imagem de Fundo Geral --- */
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: url("{image_url}");
            background-size: cover;
            background-position: center;
            filter: blur(8px);
            -webkit-filter: blur(8px);
            z-index: -1; /* Coloca a imagem atrás de todo o conteúdo */
        }}

        /* --- Estilos para o Tema Claro (Padrão) --- */
        [data-testid="stAppViewContainer"] > .main .block-container {{
            position: relative;
            background-color: rgba(255, 255, 255, 0.85); /* Fundo branco semi-transparente */
            color: #31333F; /* Texto escuro */
            border-radius: 15px;
            padding: 2rem;
            box-shadow: 0 8px 32px 0 rgba(31, 38, 135, 0.37);
        }}
        [data-testid="stExpander"] {{
            background-color: rgba(240, 242, 246, 0.90);
            border-radius: 10px;
        }}

        /* --- Estilos para o Tema Escuro --- */
        /* O seletor 'html[data-theme="dark"]' aplica estes estilos apenas quando o tema escuro está ativo */
        html[data-theme="dark"] [data-testid="stAppViewContainer"] > .main .block-container {{
            background-color: rgba(20, 20, 35, 0.85); /* Fundo escuro semi-transparente */
            color: #FAFAFA; /* Texto claro */
        }}
        html[data-theme="dark"] [data-testid="stExpander"] {{
            background-color: rgba(40, 40, 55, 0.90);
        }}
        
        /* --- Ajustes Gerais para ambos os temas --- */
        [data-testid="stHeader"], [data-testid="stTabs"] {{
            background: transparent;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# --- Funções de Gestão de Dados com GitHub ---

@st.cache_resource
def get_github_repo():
    """Autentica no GitHub e retorna o objeto do repositório."""
    try:
        github_secrets = st.secrets["github"]
        g = Github(github_secrets["token"])
        return g.get_repo(github_secrets["repo"])
    except Exception as e:
        st.error(f"Erro ao conectar com o repositório do GitHub. Verifique o secrets.toml. Detalhes: {e}")
        return None

@st.cache_data(ttl=30)
def carregar_dados_github(path, colunas):
    """Carrega o arquivo CSV do GitHub ou cria um DataFrame vazio."""
    repo = get_github_repo()
    if repo is None:
        st.warning("Não foi possível carregar os dados. Conexão com o GitHub falhou.")
        return pd.DataFrame(columns=colunas)
    try:
        file_content = repo.get_contents(path)
        content_str = file_content.decoded_content.decode("utf-8")
        return pd.read_csv(io.StringIO(content_str))
    except UnknownObjectException:
        return pd.DataFrame(columns=colunas)
    except Exception as e:
        st.error(f"Erro ao carregar dados do GitHub: {e}")
        return pd.DataFrame(columns=colunas)

def salvar_dados_github(repo, path, df, commit_message):
    """Salva o DataFrame como um arquivo CSV no GitHub com mensagens de depuração."""
    if repo is None:
        st.error("Não foi possível salvar. A conexão com o GitHub falhou.")
        return

    st.info("A preparar para salvar os dados no GitHub...")
    csv_string = df.to_csv(index=False)

    try:
        contents = repo.get_contents(path)
        st.info(f"Ficheiro '{path}' encontrado. A tentar atualizar...")
        repo.update_file(contents.path, commit_message, csv_string, contents.sha)
        st.success("Dados atualizados com sucesso no GitHub!")
        st.balloons()
    except UnknownObjectException:
        st.info(f"Ficheiro '{path}' não encontrado. A tentar criar...")
        repo.create_file(path, commit_message, csv_string)
        st.success("Ficheiro criado e dados salvos com sucesso no GitHub!")
        st.balloons()
    except Exception as e:
        st.error(f"Ocorreu um erro DETALHADO ao salvar no GitHub:")
        st.exception(e)

    st.cache_data.clear()

# --- Funções do Google Calendar (sem alterações) ---
def get_google_calendar_service():
    try:
        service_account_info = st.secrets["google_service_account"]
        if hasattr(service_account_info, "to_dict"): service_account_info = service_account_info.to_dict()
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro de autenticação com o Google. Detalhes: {e}")
        return None

def criar_evento_google_calendar(service, info_evento):
    tz = pytz.timezone(TIMEZONE)
    evento_body = {
        'summary': f"💅 {info_evento['servico_nome']} - {info_evento['cliente_nome']}",
        'description': f"Serviços: {info_evento['servico_nome']}\nValor Total: R$ {info_evento['valor_total']:.2f}",
        'start': {'dateTime': tz.localize(info_evento['inicio']).isoformat(), 'timeZone': TIMEZONE},
        'end': {'dateTime': tz.localize(info_evento['fim']).isoformat(), 'timeZone': TIMEZONE},
        'reminders': {'useDefault': False, 'overrides': [{'method': 'popup', 'minutes': 60}, {'method': 'popup', 'minutes': 1440}]},
    }
    try:
        service.events().insert(calendarId=CALENDAR_ID, body=evento_body).execute()
        return True
    except HttpError as error:
        st.error(f"Não foi possível criar o evento no Google Calendar. Erro: {error}")
        return False

# --- Interface do Aplicativo ---
st.set_page_config(page_title="Agenda de Manicure", layout="centered")
set_background(BACKGROUND_IMAGE_URL) # Adiciona o fundo aqui
st.title("💅 Agenda da Manicure")


if 'editing_service_index' not in st.session_state: st.session_state.editing_service_index = None
if 'deleting_service_index' not in st.session_state: st.session_state.deleting_service_index = None

google_service = get_google_calendar_service()
repo_github = get_github_repo()

if not google_service or not repo_github:
    st.warning("Aguardando conexão com o Google Calendar e/ou GitHub...")
    st.stop()

tab_agendar, tab_servicos, tab_consultar = st.tabs(["➕ Agendar", "✨ Serviços", "🗓️ Agenda"])

# --- Aba de Gestão de Serviços ---
with tab_servicos:
    st.header("✨ Gestão de Serviços")
    github_path_servicos = st.secrets["github"]["path"]
    # ALTERADO: O ficheiro CSV agora só tem Nome e Valor
    df_servicos = carregar_dados_github(github_path_servicos, colunas=['Nome', 'Valor'])

    if st.session_state.editing_service_index is not None:
        with st.form("form_edit_servico"):
            st.subheader("✏️ Editando Serviço")
            idx = st.session_state.editing_service_index
            servico_atual = df_servicos.iloc[idx]
            novo_nome = st.text_input("Nome", value=servico_atual['Nome'])
            novo_valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", value=float(servico_atual['Valor']))
            c1, c2 = st.columns(2)
            if c1.form_submit_button("Salvar", type="primary", use_container_width=True):
                df_servicos.at[idx, 'Nome'] = novo_nome
                df_servicos.at[idx, 'Valor'] = novo_valor
                salvar_dados_github(repo_github, github_path_servicos, df_servicos, f"Atualiza serviço: {novo_nome}")
                st.session_state.editing_service_index = None
                st.rerun()
            if c2.form_submit_button("Cancelar", use_container_width=True):
                st.session_state.editing_service_index = None
                st.rerun()

    with st.expander("Adicionar Novo Serviço", expanded=True):
        with st.form("form_add_servico", clear_on_submit=True):
            nome = st.text_input("Nome do Serviço")
            valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            if st.form_submit_button("Adicionar", type="primary"):
                if nome and valor > 0:
                    # ALTERADO: Cria a linha apenas com Nome e Valor para salvar no CSV
                    nova_linha = pd.DataFrame([{'Nome': nome, 'Valor': valor}])
                    df_servicos = pd.concat([df_servicos, nova_linha], ignore_index=True)
                    salvar_dados_github(repo_github, github_path_servicos, df_servicos, f"Adiciona serviço: {nome}")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos.")

    st.markdown("---")
    st.subheader("Serviços Cadastrados")
    if not df_servicos.empty:
        for index, row in df_servicos.iterrows():
            with st.container(border=True):
                if st.session_state.deleting_service_index == index:
                    st.warning(f"**Remover '{row['Nome']}'?**")
                    c1, c2 = st.columns(2)
                    if c1.button("Sim, remover!", key=f"del_{index}", type="primary", use_container_width=True):
                        df_servicos = df_servicos.drop(index).reset_index(drop=True)
                        salvar_dados_github(repo_github, github_path_servicos, df_servicos, f"Remove serviço: {row['Nome']}")
                        st.session_state.deleting_service_index = None
                        st.rerun()
                    if c2.button("Cancelar", key=f"cancel_del_{index}", use_container_width=True):
                        st.session_state.deleting_service_index = None
                        st.rerun()
                else:
                    c1, c2, c3 = st.columns([4, 1, 1])
                    c1.markdown(f"**{row['Nome']}**")
                    c1.caption(f"R$ {row['Valor']:.2f}")
                    if c2.button("✏️", key=f"edit_{index}", help="Editar"):
                        st.session_state.editing_service_index = index
                        st.rerun()
                    if c3.button("🗑️", key=f"del_btn_{index}", help="Remover"):
                        st.session_state.deleting_service_index = index
                        st.rerun()
    else:
        st.info("Ainda não há serviços cadastrados.")

# --- Aba de Agendamento ---
with tab_agendar:
    st.header("➕ Novo Agendamento")
    # Carrega os dados do CSV (apenas Nome e Valor)
    df_servicos_agenda = carregar_dados_github(st.secrets["github"]["path"], colunas=['Nome', 'Valor'])

    # ALTERADO: Adiciona a coluna de duração padrão em memória para o cálculo do agendamento
    if not df_servicos_agenda.empty:
        df_servicos_agenda['Duração (min)'] = DURACAO_PADRAO_MIN
    
    if df_servicos_agenda.empty:
        st.warning("⚠️ Primeiro, adicione pelo menos um serviço na aba '✨ Serviços'.")
    else:
        with st.form("form_agendamento"):
            cliente = st.text_input("👤 Nome da Cliente")
            servicos_nomes = st.multiselect("💅 Serviços Desejados", options=df_servicos_agenda['Nome'].tolist())
            c1, c2 = st.columns(2)
            data = c1.date_input("🗓️ Data")
            hora = c2.time_input("⏰ Horário")

            if servicos_nomes:
                info_servicos = df_servicos_agenda[df_servicos_agenda['Nome'].isin(servicos_nomes)]
                valor_total = info_servicos['Valor'].sum()
                # O cálculo da duração total continua a funcionar porque adicionámos a coluna em memória
                duracao_total = info_servicos['Duração (min)'].sum()
                st.info(f"Valor Total: R$ {valor_total:.2f}")
            
            if st.form_submit_button("Confirmar Agendamento", type="primary", use_container_width=True):
                if cliente and servicos_nomes and data and hora:
                    # Recalcula a duração para garantir que está correta antes de criar o evento
                    info_servicos = df_servicos_agenda[df_servicos_agenda['Nome'].isin(servicos_nomes)]
                    valor_total = info_servicos['Valor'].sum()
                    duracao_total = info_servicos['Duração (min)'].sum()

                    inicio = datetime.combine(data, hora)
                    fim = inicio + timedelta(minutes=int(duracao_total))
                    nomes_str = ", ".join(servicos_nomes)
                    evento = {"cliente_nome": cliente, "servico_nome": nomes_str, "valor_total": valor_total, "inicio": inicio, "fim": fim}
                    with st.spinner("A registar na agenda..."):
                        if criar_evento_google_calendar(google_service, evento):
                            st.success(f"Agendamento para {cliente} confirmado!")
                else:
                    st.error("Preencha todos os campos.")

# --- Aba de Consulta ---
with tab_consultar:
    st.header("🗓️ Próximos Compromissos")
    try:
        now = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        events_result = google_service.events().list(calendarId=CALENDAR_ID, timeMin=now, maxResults=15, singleEvents=True, orderBy='startTime').execute()
        eventos = events_result.get('items', [])
        if not eventos:
            st.info("Nenhum compromisso futuro encontrado.")
        else:
            for evento in eventos:
                inicio = pd.to_datetime(evento['start'].get('dateTime')).tz_convert(TIMEZONE)
                with st.container(border=True):
                    st.markdown(f"**{evento['summary']}**")
                    st.write(f"🗓️ {inicio.strftime('%d de %B, %Y às %H:%M')}")
    except Exception as e:
        st.error(f"Não foi possível buscar os agendamentos. Erro: {e}")

