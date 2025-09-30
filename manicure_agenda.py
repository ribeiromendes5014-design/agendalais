# -*- coding: utf-8 -*-
import streamlit as st
import pandas as pd
import os
import json
import pytz
from datetime import datetime, timedelta
from google.oauth2 import service_account
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

# --- Configurações Essenciais ---
# ⬇️ PASSO 1: SUBSTITUA A LINHA ABAIXO PELO E-MAIL DO CALENDÁRIO DA MANICURE ⬇️
CALENDAR_ID = "COLOQUE_O_EMAIL_DO_CALENDARIO_AQUI" 
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

        # Garante que é dict (Streamlit já entrega como dict quando usamos [google_service_account] no TOML)
        if not isinstance(service_account_info, dict):
            service_account_info = json.loads(service_account_info)

        creds = service_account.Credentials.from_service_account_info(
            dict(service_account_info), scopes=SCOPES
        )
        return build('calendar', 'v3', credentials=creds)

    except Exception as e:
        st.error(f"Erro de autenticação com o Google. Verifique o ficheiro 'secrets.toml'. Detalhes: {e}")
        return None


def criar_evento_google_calendar(service, info_evento):
    """Cria o evento no Google Calendar da manicure."""
    tz = pytz.timezone(TIMEZONE)
    evento_body = {
        'summary': f"💅 {info_evento['servico_nome']} - {info_evento['cliente_nome']}",
        'description': f"Serviço: {info_evento['servico_nome']}\nValor: R$ {info_evento['valor']:.2f}",
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
        return pd.read_csv(arquivo)
    else:
        return pd.DataFrame(columns=colunas)

def salvar_dados(df, arquivo):
    """Salva o DataFrame num ficheiro CSV."""
    df.to_csv(arquivo, index=False)

# --- Interface do Aplicativo ---
st.set_page_config(page_title="Agenda de Manicure", layout="centered")

st.title("💅 Agenda da Manicure")

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

    with st.form("form_servico", clear_on_submit=True):
        st.subheader("Adicionar Novo Serviço")
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
        st.dataframe(df_servicos, use_container_width=True)
        
        servico_para_deletar = st.selectbox("Selecione um serviço para remover:", options=df_servicos['Nome'].tolist(), index=None, placeholder="Escolha um serviço...")
        if servico_para_deletar:
            if st.button(f"Remover '{servico_para_deletar}'", type="secondary"):
                df_servicos = df_servicos[df_servicos['Nome'] != servico_para_deletar]
                salvar_dados(df_servicos, ARQUIVO_SERVICOS_CSV)
                st.success(f"Serviço '{servico_para_deletar}' removido.")
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
        with st.form("form_agendamento", clear_on_submit=True):
            cliente = st.text_input("👤 Nome da Cliente")
            
            servicos_disponiveis = df_servicos_agenda['Nome'].tolist()
            servico_selecionado = st.selectbox("💅 Serviço Desejado", options=servicos_disponiveis, index=None, placeholder="Selecione o serviço...")

            col1, col2 = st.columns(2)
            data_agendamento = col1.date_input("🗓️ Data")
            hora_agendamento = col2.time_input("⏰ Horário")
            
            info_servico = None
            if servico_selecionado:
                info_servico = df_servicos_agenda[df_servicos_agenda['Nome'] == servico_selecionado].iloc[0]
                st.info(f"Valor: R$ {info_servico['Valor']:.2f} | Duração: {info_servico['Duração (min)']} minutos")

            if st.form_submit_button("Confirmar Agendamento", type="primary", use_container_width=True):
                if cliente and servico_selecionado and data_agendamento and hora_agendamento and info_servico is not None:
                    inicio = datetime.combine(data_agendamento, hora_agendamento)
                    fim = inicio + timedelta(minutes=int(info_servico['Duração (min)']))
                    
                    info_evento = {
                        "cliente_nome": cliente,
                        "servico_nome": info_servico['Nome'],
                        "valor": info_servico['Valor'],
                        "inicio": inicio,
                        "fim": fim
                    }
                    
                    with st.spinner("A registar na agenda..."):
                        sucesso = criar_evento_google_calendar(service, info_evento)
                    
                    if sucesso:
                        st.success(f"Agendamento para {cliente} às {inicio.strftime('%H:%M')} confirmado com sucesso!")
                        # Opcional: Salvar backup local no CSV
                        df_agendamentos = carregar_dados(ARQUIVO_AGENDAMENTOS_CSV, colunas=['Cliente', 'Serviço', 'Data e Hora Início', 'Valor'])
                        novo_agendamento = pd.DataFrame([{'Cliente': cliente, 'Serviço': info_servico['Nome'], 'Data e Hora Início': inicio, 'Valor': info_servico['Valor']}])
                        df_agendamentos = pd.concat([df_agendamentos, novo_agendamento], ignore_index=True)
                        salvar_dados(df_agendamentos, ARQUIVO_AGENDAMENTOS_CSV)
                else:
                    st.error("Por favor, preencha todos os campos.")

# --- Aba de Consulta ---
with tab_consultar:
    st.header("🗓️ Próximos Compromissos")
    st.write("Aqui estão os seus próximos agendamentos, direto do Google Calendar.")

    try:
        now = datetime.now(pytz.timezone(TIMEZONE)).isoformat()
        events_result = service.events().list(
            calendarId=CALENDAR_ID, timeMin=now,
            maxResults=10, singleEvents=True,
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


