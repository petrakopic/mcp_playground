import asyncio
import nest_asyncio
import os
import streamlit as st
from pathlib import Path
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage, AIMessage
from langgraph.checkpoint.memory import InMemorySaver
from system_prompt import PROMPT

USERNAME = os.environ.get("APP_USERNAME", "admin")
PASSWORD = os.environ.get("APP_PASSWORD", "s3cret")

# --- Constants ---
MCP_COMMAND = ["uv", "run", "mcp_snowflake_server", "--account", os.environ["SNOWFLAKE_ACCOUNT"], "--warehouse", os.environ["SNOWFLAKE_WAREHOUSE"],  "--user", os.environ["SNOWFLAKE_USER"], "--password", os.environ["SNOWFLAKE_PASSWORD"], "--role", os.environ["SNOWFLAKE_ROLE"], "--database", os.environ["SNOWFLAKE_DATABASE"], "--schema", os.environ["SNOWFLAKE_SCHEMA"]]
MODEL_NAME = "claude-3-5-sonnet-latest"

ICON_PATH='shovels_chuck.png'
nest_asyncio.apply()

ASSISTANT_NAME  = "Chuck"
ASSISTANT_AVATAR="🤖"

if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    st.session_state.event_loop = loop
    asyncio.set_event_loop(loop)



def get_final_answer(answers:list[str]):
    agent_log = ". ".join([str(answer) for answer in answers])

    instruction = ("""Rewrite the agent's answer into a single, clear response.""")   
    user_content = instruction + agent_log

    # Initialize the model
    chat = ChatAnthropic(
        model_name=MODEL_NAME,
        temperature=0, 
        timeout=60.0, 
        stop_sequences=None
    )

    # Send the combined prompt
    response = chat.invoke([HumanMessage(content=user_content)], timeout=60.0, stop_sequences=None)
    return response.content


st.set_page_config(page_title="Shovels AI Chat (Alpha)", page_icon=ICON_PATH, layout="wide")

def check_password() -> bool:
    """Return True if the user has entered correct credentials."""
    def _unlock():
        if (st.session_state["username"] == USERNAME
                and st.session_state["password"] == PASSWORD):
            st.session_state["auth_ok"] = True
            # Don’t store creds in session after check
            for key in ("username", "password"):
                del st.session_state[key]
        else:
            st.session_state["auth_ok"] = False

    if "auth_ok" not in st.session_state:
        # first visit – ask for creds
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password", on_change=_unlock)
        return False

    if not st.session_state["auth_ok"]:
        # wrong creds – ask again
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password", on_change=_unlock)
        st.error("⛔ Incorrect user or password")
        return False

    return True

if not check_password():
    st.stop()        


st.image(ICON_PATH, width=100)
st.title("Chuck — Shovels AI Assistant")
st.caption("Chuck knows every permit. Every contractor. Nationwide.")

# --- Agent setup ---
async def setup_agent():
    server_params = StdioServerParameters(command=MCP_COMMAND[0], args=MCP_COMMAND[1:])
    stdio_ctx = stdio_client(server_params)
    st.session_state.stdio_ctx = stdio_ctx
    st.session_state.mcp_client = await stdio_ctx.__aenter__()
    read, write = st.session_state.mcp_client
    client_session = ClientSession(read, write)
    await client_session.__aenter__()
    await client_session.initialize()
    tools = await load_mcp_tools(client_session)
    model = ChatAnthropic(model_name=MODEL_NAME)
    agent = create_react_agent(model, tools, prompt=PROMPT)
    st.session_state.agent = agent
    st.session_state.client_session = client_session

if "agent" not in st.session_state:
    st.session_state.event_loop.run_until_complete(setup_agent())

if "history" not in st.session_state:
    st.session_state.history = []

for role, msg in st.session_state.history:
    st.chat_message(role).markdown(msg)

# --- Query execution ---
def get_answer_sync(query: str):
    async def _run():
        result = await st.session_state.agent.ainvoke({"messages": [HumanMessage(content=query)]})
        messages = result.get("messages", [])
        print(messages)
        return messages
    return st.session_state.event_loop.run_until_complete(_run())

prompt = st.chat_input("Type your question and press Enter…")
if prompt:
    st.session_state.history.append(("user", prompt))
    st.chat_message("user").markdown(prompt)

    with st.chat_message(ASSISTANT_NAME, avatar=ASSISTANT_AVATAR):
        placeholder = st.empty()
        placeholder.markdown("⌛ Thinking...")
        try:
            answers = get_answer_sync(prompt)
            #print(answers)
            if answers: 
                final_answer = get_final_answer(answers)
            else: 
                final_answer = "I am sorry but I could not answer that question."
        except Exception as e:
            final_answer = f"❌ Error: {e}"
        placeholder.markdown(final_answer)
        st.session_state.history.append((ASSISTANT_NAME, final_answer))

with st.sidebar.expander("ℹ️ About", expanded=False):
    
    st.markdown("This is a chatbot that can answer questions about Shovels data. ")

    st.markdown("The chatbox is powered by [Claude 3.5 Sonnet](https://docs.anthropic.com/en/docs/models/claude-3-5-sonnet) and ")
    st.markdown("Learn more about [shovels.ai](https://shovels.ai) or check out our [data dictionary](https://docs.shovels.ai/docs/introduction)")


with st.sidebar.expander("💡 Example prompts", expanded=False):
    st.markdown("- What is the count of solar installations in LOS ANGELES in 2025? ")
    st.markdown("- Describe me the PERMITS table. ")
    st.markdown("- How many permits were issued for new construction last year? ") 
    st.markdown("- What is the average permit duration in FL? ") 
