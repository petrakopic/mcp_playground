import asyncio
import nest_asyncio
import os
import streamlit as st
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
from langchain_mcp_adapters.tools import load_mcp_tools
from langgraph.prebuilt import create_react_agent
from langchain_anthropic import ChatAnthropic
from langchain.schema import HumanMessage, AIMessage
from langgraph.checkpoint.memory import InMemorySaver



# --- Constants ---
MCP_COMMAND = ["uv", "run", "mcp_snowflake_server", "--account", os.environ["SNOWFLAKE_ACCOUNT"], "--warehouse", os.environ["SNOWFLAKE_WAREHOUSE"],  "--user", os.environ["SNOWFLAKE_USER"], "--password", os.environ["SNOWFLAKE_PASSWORD"], "--role", os.environ["SNOWFLAKE_ROLE"], "--database", os.environ["SNOWFLAKE_DATABASE"], "--schema", os.environ["SNOWFLAKE_SCHEMA"]]

MODEL_NAME = "claude-3-5-sonnet-latest"
PROMPT = """
Step 1: Understand the question
Read the user's question carefully.
If there are multiple questions, split them up.

Step 2:
Think like a senior data analyst
Write focused, efficient SQL.
Use only the columns that exist in the table.
Use the SHOVELS.SHOVELS schema and PERMITS table by default.

Step 3: Filter data
Use boolean columns to filter data, e.g. SOLAR=TRUE for solar permits, new_construction=TRUE for new construction permits,
hvac=TRUE for hvac permits, etc.
Use start_date as the default filter for date columns.
If user is interested in a specific year, use YEAR(start_date) bigint as a filter.
All personal nouns are always uppercase, e.g. "LOS ANGELES"
Ensure you use the correct column names.

Step 3: Check your work
If there’s an error, check if you used the wrong column.
"""

ICON_PATH='shovels-online.svg'
nest_asyncio.apply()

if "event_loop" not in st.session_state:
    loop = asyncio.new_event_loop()
    st.session_state.event_loop = loop
    asyncio.set_event_loop(loop)

# --- Streamlit config ---

st.set_page_config(page_title="Shovels AI Chat", page_icon=ICON_PATH, layout="wide")
st.image(ICON_PATH)
st.title("Shovels AI Chat (Alpha)")
st.markdown("⚠️ **Note:** this app is under heavy development.") 
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
        texts = []
        for m in messages:
            if isinstance(m, AIMessage):
                content = m.content
                if isinstance(content, str):
                    texts.append(content)
                elif isinstance(content, list):
                    texts.extend(d["text"] for d in content if d.get("type") == "text")
        return texts
    return st.session_state.event_loop.run_until_complete(_run())

prompt = st.chat_input("Type your question and press Enter…")
if prompt:
    st.session_state.history.append(("user", prompt))
    st.chat_message("user").markdown(prompt)

    with st.chat_message("assistant", avatar="🤖"):
        placeholder = st.empty()
        placeholder.markdown("⌛ Thinking...")
        try:
            answers = get_answer_sync(prompt)
            #print(answers)
            
            final_answer = answers[-1] if answers else "No response."
            final_answer = final_answer.replace("Let me add this insight to the memo:", "")
        except Exception as e:
            final_answer = f"❌ Error: {e}"
        placeholder.markdown(final_answer)
        st.session_state.history.append(("assistant", final_answer))

with st.sidebar.expander("ℹ️ About", expanded=False):
    
    st.markdown("This is a chatbot that can answer questions about Shovels data. ")

    st.markdown("The chatbox is powered by [Claude 3.5 Sonnet](https://docs.anthropic.com/en/docs/models/claude-3-5-sonnet) and ")
    st.markdown("Learn more about [shovels.ai](https://shovels.ai) or check out our [data dictionary](https://docs.shovels.ai/docs/introduction)")


with st.sidebar.expander("💡 Example prompts", expanded=False):
    st.markdown("- What is the count of solar installations in LOS ANGELES in 2025? ")
    st.markdown("- Describe me the PERMITS table. ")
    st.markdown("- How many permits were issued for new construction last year? ") 
    st.markdown("- What is the average permit duration in CA? ") 
