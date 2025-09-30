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
DURACAO_PADRAO_MIN = 60

# --- Configuração do Fundo ---
BACKGROUND_IMAGE_URL = "https://i.ibb.co/rK42GP6m/background.jpg"

def set_background(image_url):
    st.markdown(
        f"""
        <style>
        .stApp::before {{
            content: "";
            position: fixed;
            top: 0; left: 0; right: 0; bottom: 0;
            background-image: url("{image_url}");
            background-size: cover;
            background-position: center;
            filter: blur(8px);
            -webkit-filter: blur(8px);
            z-index: 0;
        }}
        [data-testid="stAppViewContainer"] > .main .block-container {{
            position: relative;
            z-index: 1;
            background-color: rgba(255, 255, 255, 0.0);
        }}
        [data-testid="stHeader"], [data-testid="stTabs"] {{
            background: transparent;
        }}
        .dark-box {{
            background-color: rgba(0, 0, 0, 0.6);
            padding: 1rem;
            border-radius: 12px;
            margin-bottom: 1rem;
            border: 1px solid rgba(255,255,255,0.2);
        }}
        .dark-box * {{
            color: white !important;
        }}
        </style>
        """,
        unsafe_allow_html=True
    )

# --- Funções GitHub ---
@st.cache_resource
def get_github_repo():
    try:
        github_secrets = st.secrets["github"]
        g = Github(github_secrets["token"])
        return g.get_repo(github_secrets["repo"])
    except Exception as e:
        st.error(f"Erro ao conectar com o GitHub. Detalhes: {e}")
        return None

@st.cache_data(ttl=30)
def carregar_dados_github(path, colunas):
    repo = get_github_repo()
    if repo is None:
        return pd.DataFrame(columns=colunas)
    try:
        file_content = repo.get_contents(path)
        content_str = file_content.decoded_content.decode("utf-8")
        return pd.read_csv(io.StringIO(content_str))
    except UnknownObjectException:
        return pd.DataFrame(columns=colunas)
    except Exception as e:
        st.error(f"Erro ao carregar dados: {e}")
        return pd.DataFrame(columns=colunas)

def salvar_dados_github(repo, path, df, commit_message):
    if repo is None:
        st.error("Falha ao salvar no GitHub.")
        return
    csv_string = df.to_csv(index=False)
    try:
        contents = repo.get_contents(path)
        repo.update_file(contents.path, commit_message, csv_string, contents.sha)
    except UnknownObjectException:
        repo.create_file(path, commit_message, csv_string)
    except Exception as e:
        st.error(f"Erro ao salvar no GitHub: {e}")
    st.cache_data.clear()

# --- Google Calendar ---
def get_google_calendar_service():
    try:
        service_account_info = st.secrets["google_service_account"]
        if hasattr(service_account_info, "to_dict"): 
            service_account_info = service_account_info.to_dict()
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro Google: {e}")
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
        st.error(f"Erro ao criar evento: {error}")
        return False

# --- Interface ---
st.set_page_config(page_title="Agenda de Manicure", layout="centered")
set_background(BACKGROUND_IMAGE_URL)
st.title("💅 Agenda da Manicure")

if 'editing_service_index' not in st.session_state: 
    st.session_state.editing_service_index = None
if 'deleting_service_index' not in st.session_state: 
    st.session_state.deleting_service_index = None

google_service = get_google_calendar_service()
repo_github = get_github_repo()
if not google_service or not repo_github:
    st.warning("Aguardando conexão com o Google Calendar e GitHub...")
    st.stop()

tab_agendar, tab_servicos, tab_consultar = st.tabs(["➕ Agendar", "✨ Serviços", "🗓️ Agenda"])

# --- Aba Serviços ---
with tab_servicos:
    st.markdown('<div class="dark-box"><h2>✨ Gestão de Serviços</h2></div>', unsafe_allow_html=True)
    github_path_servicos = st.secrets["github"]["path"]
    df_servicos = carregar_dados_github(github_path_servicos, colunas=['Nome', 'Valor'])

    if st.session_state.editing_service_index is not None:
        with st.form("form_edit_servico"):
            st.markdown('<div class="dark-box"><h3>✏️ Editando Serviço</h3>', unsafe_allow_html=True)
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
            st.markdown('</div>', unsafe_allow_html=True)

    with st.expander("Adicionar Novo Serviço", expanded=True):
        with st.form("form_add_servico", clear_on_submit=True):
            nome = st.text_input("Nome do Serviço")
            valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            if st.form_submit_button("Adicionar", type="primary"):
                if nome and valor > 0:
                    nova_linha = pd.DataFrame([{'Nome': nome, 'Valor': valor}])
                    df_servicos = pd.concat([df_servicos, nova_linha], ignore_index=True)
                    salvar_dados_github(repo_github, github_path_servicos, df_servicos, f"Adiciona serviço: {nome}")
                    st.rerun()
                else:
                    st.error("Preencha todos os campos.")

    st.markdown('<div class="dark-box" style="text-align:center;"><h3>Serviços Cadastrados</h3></div>', unsafe_allow_html=True)

    if not df_servicos.empty:
        for index, row in df_servicos.iterrows():
            st.markdown('<div class="dark-box">', unsafe_allow_html=True)
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
                c1.markdown(f"<span style='color:white; font-weight:bold;'>{row['Nome']}</span>", unsafe_allow_html=True)
                c1.markdown(f"<span style='color:white;'>R$ {row['Valor']:.2f}</span>", unsafe_allow_html=True)
                if c2.button("✏️", key=f"edit_{index}", help="Editar"):
                    st.session_state.editing_service_index = index
                    st.rerun()
                if c3.button("🗑️", key=f"del_btn_{index}", help="Remover"):
                    st.session_state.deleting_service_index = index
                    st.rerun()
            st.markdown('</div>', unsafe_allow_html=True)
    else:
        st.markdown('<div class="dark-box"><p>Ainda não há serviços cadastrados.</p></div>', unsafe_allow_html=True)

# --- Aba Agendamento ---
with tab_agendar:
    st.markdown('<div class="dark-box"><h2>➕ Novo Agendamento</h2></div>', unsafe_allow_html=True)
    df_servicos_agenda = carregar_dados_github(st.secrets["github"]["path"], colunas=['Nome', 'Valor'])
    if not df_servicos_agenda.empty:
        df_servicos_agenda['Duração (min)'] = DURACAO_PADRAO_MIN
    if df_servicos_agenda.empty:
        st.markdown('<div class="dark-box"><p>⚠️ Primeiro, adicione pelo menos um serviço na aba "✨ Serviços".</p></div>', unsafe_allow_html=True)
    else:
        with st.form("form_agendamento"):
            st.markdown('<div class="dark-box">', unsafe_allow_html=True)
            cliente = st.text_input("👤 Nome da Cliente")
            servicos_nomes = st.multiselect("💅 Serviços Desejados", options=df_servicos_agenda['Nome'].tolist())
            c1, c2 = st.columns(2)
            data = c1.date_input("🗓️ Data")
            hora = c2.time_input("⏰ Horário")
            if servicos_nomes:
                info_servicos = df_servicos_agenda[df_servicos_agenda['Nome'].isin(servicos_nomes)]
                valor_total = info_servicos['Valor'].sum()
                duracao_total = info_servicos['Duração (min)'].sum()
                st.markdown(f"<p style='color:white;'>Valor Total: R$ {valor_total:.2f}</p>", unsafe_allow_html=True)

            if st.form_submit_button("Confirmar Agendamento", type="primary", use_container_width=True):
                if cliente and servicos_nomes and data and hora:
                    info_servicos = df_servicos_agenda[df_servicos_agenda['Nome'].isin(servicos_nomes)]
                    valor_total = info_servicos['Valor'].sum()
                    duracao_total = info_servicos['Duração (min)'].sum()
                    inicio = datetime.combine(data, hora)
                    fim = inicio + timedelta(minutes=int(duracao_total))
                    nomes_str = ", ".join(servicos_nomes)
                    evento = {"cliente_nome": cliente, "servico_nome": nomes_str, "valor_total": valor_total, "inicio": inicio, "fim": fim}
                    with st.spinner("Registrando na agenda..."):
                        if criar_evento_google_calendar(google_service, evento):
                            st.success(f"Agendamento para {cliente} confirmado!")
                            # 👉 Salva a aba atual e força recarregar
                            st.session_state.active_tab = "agendar"
                            st.rerun()
                else:
                    st.error("Preencha todos os campos.")
            st.markdown('</div>', unsafe_allow_html=True)


# --- Aba Consulta ---
with tab_consultar:
    st.markdown('<div class="dark-box"><h2>🗓️ Próximos Compromissos</h2></div>', unsafe_allow_html=True)
    try:
        now = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        events_result = google_service.events().list(calendarId=CALENDAR_ID, timeMin=now, maxResults=15, singleEvents=True, orderBy='startTime').execute()
        eventos = events_result.get('items', [])
        if not eventos:
            st.markdown('<div class="dark-box"><p>Nenhum compromisso futuro encontrado.</p></div>', unsafe_allow_html=True)
        else:
            for evento in eventos:
                inicio = pd.to_datetime(evento['start'].get('dateTime')).tz_convert(TIMEZONE)
                st.markdown('<div class="dark-box">', unsafe_allow_html=True)
                st.markdown(f"<p style='color:white; font-weight:bold;'>{evento['summary']}</p>", unsafe_allow_html=True)
                st.markdown(f"<p style='color:white;'>🗓️ {inicio.strftime('%d de %B, %Y às %H:%M')}</p>", unsafe_allow_html=True)
                st.markdown('</div>', unsafe_allow_html=True)
    except Exception as e:
        st.markdown(f'<div class="dark-box"><p>Erro ao buscar agendamentos: {e}</p></div>', unsafe_allow_html=True)

