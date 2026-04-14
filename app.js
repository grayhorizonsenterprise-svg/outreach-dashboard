import express from "express";
import fetch from "node-fetch";

const app = express();
app.use(express.json());

const API_KEY = process.env.ANTHROPIC_API_KEY;

// =====================
// 🧠 Niche Prompts
// =====================
function getPrompt(niche) {
  if (niche === "dentist") {
    return `
You are a dental receptionist.

Handle:
- bookings
- insurance
- scheduling

Ask for:
- name
- phone
- time

Be friendly and human.
`;
  }

  if (niche === "hvac") {
    return `
You are an HVAC assistant.

Handle:
- repairs
- emergency calls

Ask for:
- name
- address
- issue urgency

Be efficient and direct.
`;
  }

  return `
You are an HOA assistant for Gray Horizons.

Handle:
- violations
- disputes

Ask for:
- name
- unit
- issue

Be calm and helpful.
`;
}

// =====================
// 🧠 Memory Store
// =====================
let sessions = {};

// =====================
// 🎙️ AI Endpoint
// =====================
app.post("/voice", async (req, res) => {
  const { message, sessionId, niche } = req.body;

  if (!sessions[sessionId]) {
    sessions[sessionId] = [];
  }

  sessions[sessionId].push({
    role: "user",
    content: message,
  });

  try {
    const response = await fetch("https://api.anthropic.com/v1/messages", {
      method: "POST",
      headers: {
        "x-api-key": API_KEY,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
      },
      body: JSON.stringify({
        model: "claude-3-haiku-20240307",
        max_tokens: 200,
        messages: sessions[sessionId],
        system: getPrompt(niche),
      }),
    });

    const data = await response.json();
    const reply = data.content?.[0]?.text || "Error";

    sessions[sessionId].push({
      role: "assistant",
      content: reply,
    });

    res.json({ reply });

  } catch (err) {
    console.error(err);
    res.json({ reply: "Error processing request" });
  }
});

// =====================
// 🌐 FRONTEND
// =====================
app.get("/", (req, res) => {
  res.send(`
<!DOCTYPE html>
<html>
<head>
  <title>AI Voice Demo</title>
</head>
<body>

<h2>📞 AI Voice Agent Demo</h2>

<select id="niche">
  <option value="hoa">HOA</option>
  <option value="dentist">Dentist</option>
  <option value="hvac">HVAC</option>
</select>

<div id="chat"></div>

<button onclick="startListening()">🎤 Start Talking</button>

<script>
let sessionId = Date.now();

// 🎤 Speech Recognition
const recognition = new (window.SpeechRecognition || window.webkitSpeechRecognition)();
recognition.lang = "en-US";

recognition.onresult = async (event) => {
  const text = event.results[0][0].transcript;

  addMessage("You", text);

  const res = await fetch("/voice", {
    method: "POST",
    headers: {"Content-Type": "application/json"},
    body: JSON.stringify({
      message: text,
      sessionId,
      niche: document.getElementById("niche").value
    })
  });

  const data = await res.json();

  speak(data.reply);
  addMessage("AI", data.reply);
};

function startListening() {
  recognition.start();
}

// 🔊 Text to Speech
function speak(text) {
  const utter = new SpeechSynthesisUtterance(text);
  speechSynthesis.speak(utter);
}

// 💬 Chat display
function addMessage(sender, text) {
  document.getElementById("chat").innerHTML +=
    "<p><b>" + sender + ":</b> " + text + "</p>";
}
</script>

</body>
</html>
  `);
});

// =====================
// 🚀 START SERVER
// =====================
app.listen(3000, () => {
  console.log("Running on http://localhost:3000");
});