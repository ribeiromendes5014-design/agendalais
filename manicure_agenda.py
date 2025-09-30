# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import pytz
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configurações Essenciais ---
# ⬇️ PASSO 1: SUBSTITUA A LINHA ABAIXO PELO E-MAIL DO CALENDÁRIO DA MANICURE ⬇️
CALENDAR_ID = "manicurelais96@gmail.com"
# Exemplo: CALENDAR_ID = "nomedamanicure@gmail.com"

ARQUIVO_SERVICOS_CSV = "servicos_manicure.csv"
ARQUIVO_AGENDAMENTOS_CSV = "agendamentos_manicure.csv"
TIMEZONE = 'America/Sao_Paulo'
SCOPES = ['https://www.googleapis.com/auth/calendar']

# --- Funções de Autenticação e API ---
def get_google_calendar_service():
    """Autentica na API do Google Calendar usando os secrets."""
    try:
        service_account_info = st.secrets["google_service_account"]
        if hasattr(service_account_info, "to_dict"):
            service_account_info = service_account_info.to_dict()
        if not isinstance(service_account_info, dict):
            raise ValueError("Configuração inválida em secrets.toml. Deve ser um [google_service_account] com chaves internas.")
        creds = service_account.Credentials.from_service_account_info(service_account_info, scopes=SCOPES)
        return build('calendar', 'v3', credentials=creds)
    except Exception as e:
        st.error(f"Erro de autenticação com o Google. Verifique o ficheiro 'secrets.toml'. Detalhes: {e}")
        return None

def criar_evento_google_calendar(service, info_evento):
    """Cria o evento no Google Calendar da manicure."""
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

# --- Funções de Gestão de Dados (Serviços e Agendamentos) ---
def carregar_dados(arquivo, colunas):
    """Carrega um ficheiro CSV ou cria um novo se não existir."""
    if os.path.exists(arquivo):
        try:
            return pd.read_csv(arquivo)
        except pd.errors.EmptyDataError:
            return pd.DataFrame(columns=colunas)
    else:
        return pd.DataFrame(columns=colunas)

def salvar_dados(df, arquivo):
    """Salva o DataFrame num ficheiro CSV."""
    df.to_csv(arquivo, index=False)

# --- Interface do Aplicativo ---
st.set_page_config(page_title="Agenda de Manicure", layout="centered")

st.title("💅 Agenda da Manicure")

# Inicializar o estado da sessão para edição e exclusão
if 'editing_service_index' not in st.session_state:
    st.session_state.editing_service_index = None
if 'deleting_service_index' not in st.session_state:
    st.session_state.deleting_service_index = None

service = get_google_calendar_service()

if not service:
    st.stop()

if CALENDAR_ID == "COLOQUE_O_EMAIL_DO_CALENDARIO_AQUI":
    st.error("Atenção: É necessário configurar o CALENDAR_ID no código para que o sistema funcione.")
    st.stop()

tab_agendar, tab_servicos, tab_consultar = st.tabs(["➕ Agendar", "✨ Serviços", "🗓️ Agenda"])

# --- Aba de Gestão de Serviços ---
with tab_servicos:
    st.header("✨ Gestão de Serviços")
    st.write("Adicione, edite ou remova os serviços que você oferece.")

    df_servicos = carregar_dados(ARQUIVO_SERVICOS_CSV, colunas=['Nome', 'Valor', 'Duração (min)'])

    # Formulário para EDITAR um serviço (aparece no topo quando ativado)
    if st.session_state.editing_service_index is not None:
        with st.form("form_edit_servico"):
            st.subheader("✏️ Editando Serviço")
            idx = st.session_state.editing_service_index
            servico_atual = df_servicos.iloc[idx]
            
            novo_nome = st.text_input("Nome do Serviço", value=servico_atual['Nome'])
            novo_valor = st.number_input("Valor (R$)", min_value=0.0, format="%.2f", value=float(servico_atual['Valor']))
            nova_duracao = st.number_input("Duração (em minutos)", min_value=15, step=5, value=int(servico_atual['Duração (min)']))

            col1, col2 = st.columns(2)
            if col1.form_submit_button("Salvar Alterações", type="primary", use_container_width=True):
                df_servicos.at[idx, 'Nome'] = novo_nome
                df_servicos.at[idx, 'Valor'] = novo_valor
                df_servicos.at[idx, 'Duração (min)'] = nova_duracao
                salvar_dados(df_servicos, ARQUIVO_SERVICOS_CSV)
                st.success(f"Serviço '{novo_nome}' atualizado com sucesso!")
                st.session_state.editing_service_index = None
                st.rerun()
            
            if col2.form_submit_button("Cancelar", use_container_width=True):
                st.session_state.editing_service_index = None
                st.rerun()

    # Formulário para ADICIONAR um novo serviço
    with st.expander("Adicionar Novo Serviço", expanded=True):
        with st.form("form_add_servico", clear_on_submit=True):
            nome_servico = st.text_input("Nome do Serviço (ex: Pé e Mão)")
            valor_servico = st.number_input("Valor (R$)", min_value=0.0, format="%.2f")
            duracao_servico = st.number_input("Duração (em minutos)", min_value=15, step=5)
            
            if st.form_submit_button("Adicionar Serviço", type="primary"):
                if nome_servico and valor_servico > 0 and duracao_servico > 0:
                    nova_linha = pd.DataFrame([{'Nome': nome_servico, 'Valor': valor_servico, 'Duração (min)': duracao_servico}])
                    df_servicos = pd.concat([df_servicos, nova_linha], ignore_index=True)
                    salvar_dados(df_servicos, ARQUIVO_SERVICOS_CSV)
                    st.success(f"Serviço '{nome_servico}' adicionado com sucesso!")
                    st.rerun()
                else:
                    st.error("Por favor, preencha todos os campos corretamente.")

    st.markdown("---")
    st.subheader("Serviços Cadastrados")
    
    if not df_servicos.empty:
        for index, row in df_servicos.iterrows():
            with st.container(border=True):
                # Se o serviço estiver marcado para exclusão, mostra a confirmação
                if st.session_state.deleting_service_index == index:
                    st.warning(f"**Tem a certeza que deseja remover o serviço '{row['Nome']}'?**")
                    col1, col2 = st.columns(2)
                    if col1.button("Sim, remover!", key=f"confirm_delete_{index}", type="primary", use_container_width=True):
                        df_servicos = df_servicos.drop(index)
                        salvar_dados(df_servicos, ARQUIVO_SERVICOS_CSV)
                        st.success(f"Serviço '{row['Nome']}' removido.")
                        st.session_state.deleting_service_index = None
                        st.rerun()
                    if col2.button("Cancelar", key=f"cancel_delete_{index}", use_container_width=True):
                        st.session_state.deleting_service_index = None
                        st.rerun()
                # Visualização normal do serviço com botões
                else:
                    col1, col2, col3 = st.columns([4, 1, 1])
                    with col1:
                        st.markdown(f"**{row['Nome']}**")
                        st.caption(f"Valor: R$ {row['Valor']:.2f} | Duração: {row['Duração (min)']} min")
                    with col2:
                        if st.button("✏️", key=f"edit_{index}", help="Editar serviço"):
                            st.session_state.editing_service_index = index
                            st.session_state.deleting_service_index = None
                            st.rerun()
                    with col3:
                        if st.button("🗑️", key=f"delete_{index}", help="Remover serviço"):
                            st.session_state.deleting_service_index = index
                            st.session_state.editing_service_index = None
                            st.rerun()

    else:
        st.info("Ainda não há serviços cadastrados. Adicione um no formulário acima.")


# --- Aba de Agendamento ---
with tab_agendar:
    st.header("➕ Novo Agendamento")
    df_servicos_agenda = carregar_dados(ARQUIVO_SERVICOS_CSV, colunas=['Nome', 'Valor', 'Duração (min)'])

    if df_servicos_agenda.empty:
        st.warning("⚠️ Para agendar, primeiro adicione pelo menos um serviço na aba '✨ Serviços'.")
    else:
        with st.form("form_agendamento", clear_on_submit=False):
            cliente = st.text_input("👤 Nome da Cliente")
            
            servicos_disponiveis = df_servicos_agenda['Nome'].tolist()
            servicos_selecionados_nomes = st.multiselect(
                "💅 Serviços Desejados", 
                options=servicos_disponiveis, 
                placeholder="Selecione um ou mais serviços..."
            )

            col1, col2 = st.columns(2)
            data_agendamento = col1.date_input("🗓️ Data")
            hora_agendamento = col2.time_input("⏰ Horário")
            
            valor_total = 0
            duracao_total = 0
            info_servicos = None

            if servicos_selecionados_nomes:
                info_servicos = df_servicos_agenda[df_servicos_agenda['Nome'].isin(servicos_selecionados_nomes)]
                valor_total = info_servicos['Valor'].sum()
                duracao_total = info_servicos['Duração (min)'].sum()
                st.info(f"Valor Total: R$ {valor_total:.2f} | Duração Total: {duracao_total} minutos")

            if st.form_submit_button("Confirmar Agendamento", type="primary", use_container_width=True):
                if cliente and servicos_selecionados_nomes and data_agendamento and hora_agendamento and not info_servicos.empty:
                    inicio = datetime.combine(data_agendamento, hora_agendamento)
                    fim = inicio + timedelta(minutes=int(duracao_total))
                    
                    nomes_servicos_str = ", ".join(servicos_selecionados_nomes)

                    info_evento = {
                        "cliente_nome": cliente,
                        "servico_nome": nomes_servicos_str,
                        "valor_total": valor_total,
                        "inicio": inicio,
                        "fim": fim
                    }
                    
                    with st.spinner("A registar na agenda..."):
                        sucesso = criar_evento_google_calendar(service, info_evento)
                    
                    if sucesso:
                        st.success(f"Agendamento para {cliente} às {inicio.strftime('%H:%M')} confirmado com sucesso!")
                        df_agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS_CSV, colunas=['Cliente', 'Serviço', 'Data e Hora Início', 'Valor'])
                        novo_agendamento = pd.DataFrame([{'Cliente': cliente, 'Serviço': nomes_servicos_str, 'Data e Hora Início': inicio, 'Valor': valor_total}])
                        df_agendamentos = pd.concat([df_agendamentos, novo_agendamento], ignore_index=True)
                        salvar_dados(df_agendamentos, ARQUIVO_AGENDAMENTOS_CSV)
                        # Limpar campos manualmente, pois clear_on_submit=False
                        st.session_state.agendamento_realizado = True
                else:
                    st.error("Por favor, preencha todos os campos e selecione pelo menos um serviço.")

# --- Aba de Consulta ---
with tab_consultar:
    st.header("🗓️ Próximos Compromissos")
    st.write("Aqui estão os seus próximos agendamentos, direto do Google Calendar.")

    try:
        now = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        events_result = service.events().list(
            calendarId=CALENDAR_ID, timeMin=now,
            maxResults=15, singleEvents=True,
            orderBy='startTime'
        ).execute()
        eventos = events_result.get('items', [])

        if not eventos:
            st.info("Nenhum compromisso futuro encontrado na agenda.")
        else:
            for evento in eventos:
                inicio = pd.to_datetime(evento['start'].get('dateTime', evento['start'].get('date'))).tz_convert(TIMEZONE)
                with st.container(border=True):
                    st.markdown(f"**{evento['summary']}**")
                    st.write(f"🗓️ {inicio.strftime('%d de %B, %Y às %H:%M')}")

    except HttpError as error:
        st.error(f"Não foi possível buscar os agendamentos do Google Calendar. Erro: {error}")
