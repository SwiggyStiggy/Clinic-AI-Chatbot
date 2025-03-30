import openai
import sys
import os
import json
import dotenv
from PyQt6.QtWidgets import (
    QApplication, QMainWindow, QVBoxLayout, QHBoxLayout, QWidget,
    QTextEdit, QLineEdit, QPushButton, QInputDialog
)
from fpdf import FPDF, XPos, YPos

# API KEY
dotenv.load_dotenv()
openai.api_key = os.getenv('OPENAI_API_KEY')


# Description for the AI.
SYSTEM_PROMPT = (
    "You are a clinical chatbot designed to collect patient information for doctor evaluation. "
    "Your responses must remain strictly objective and neutral, without expressing sympathy, empathy, or emotion. "
    "Do not offer any diagnoses or assumptions regarding the patient's condition. Instead, you are to ask direct, necessary questions to gather the relevant information. "
    "Begin the conversation with: 'Hello! I am here to assist your doctor by gathering the necessary details from you. What symptoms are you currently experiencing?' "
    "After each patient response, ask one follow-up question at a time. For example: "
    "After receiving the patient's description of their symptoms, ask about the duration of the symptoms. "
    "Subsequently, ask about the severity of the symptoms, and then inquire if there is any additional information the patient wishes to provide. "
    "Once all the necessary information has been collected, finalize the conversation with a statement along the lines of: "
    "'Thank you for providing the details to my questions. I will now generate a report summarizing our conversation for your doctor.' "
    "'Thank you for answering my questions. Your doctor will now receive the report from our conversation and assist you with the diagnosis.' "
    "Under no circumstances should you return the report to the patient in the chat. You must memorize the patient's responses and incorporate them into a PDF report instead. "
    "Ensure all patient responses are retained in memory. "
    "Upon completion of the conversation, generate a PDF report for the doctor that includes the following sections: "
    "Symptoms, Duration, Severity, Additional Information, and AI's Assumptions (a 'near diagnosis' based on the conversation). "
    "The 'near diagnosis' should be provided in the final section of the PDF, where you document your assumption of the diagnosis. This will assist the doctor in making the final diagnosis."
)

def get_ai_response(conversation_history, user_input):
    conversation_history.append({"role": "user", "content": user_input})
    messages = [{"role": "system", "content": SYSTEM_PROMPT}] + conversation_history

    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=messages,
            temperature=0.1
        )
        ai_message = response.choices[0].message['content'].strip()
        conversation_history.append({"role": "assistant", "content": ai_message})
        return ai_message
    except Exception as e:
        return f"Error: {str(e)}"

def generate_summary(conversation_history):
    """
    Generate a concise summary for the following sections based on the conversation history:
    Symptoms, Duration, Severity, and Additional Info.
    The output should be valid JSON with keys: "Symptoms", "Duration", "Severity", "Additional Info".
    """
    conversation_json = json.dumps(conversation_history, indent=2)
    prompt = (
        "Based on the following conversation in JSON format, provide a concise summary for each of the following sections: "
        "Symptoms, Duration, Severity, and Additional Info. Your answer should be in valid JSON format as shown below:\n"
        '{\n  "Symptoms": "...",\n  "Duration": "...",\n  "Severity": "...",\n  "Additional Info": "..." \n}\n'
        "Only output valid JSON.\n\n"
        "Conversation JSON:\n" + conversation_json
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
        )
        summary_str = response.choices[0].message["content"].strip()
        summary = json.loads(summary_str)
        return summary
    except Exception as e:
        return {
            "Symptoms": "Error generating summary.",
            "Duration": "Error generating summary.",
            "Severity": "Error generating summary.",
            "Additional Info": "Error generating summary."
        }

def generate_near_diagnosis(conversation_history):
    """
    Analyze the conversation history (in JSON format) and generate a concise near diagnosis.
    This near diagnosis is intended solely for the doctor's review.
    """
    conversation_json = json.dumps(conversation_history, indent=2)
    prompt = (
        "You are a medical analysis assistant. Analyze the following conversation between a clinical chatbot and a patient (in JSON format). "
        "Based on the patient's responses, generate a concise near diagnosis (an assumption) that may assist a doctor in further evaluation. "
        "Return only the near diagnosis in couple of sentences and explain why.\n\n"
        "Conversation JSON:\n" + conversation_json
    )
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[{"role": "system", "content": prompt}],
            temperature=0.2,
        )
        near_diagnosis = response.choices[0].message["content"].strip()
        return near_diagnosis
    except Exception as e:
        return f"Error generating near diagnosis: {str(e)}"

class ChatWindow(QMainWindow):
    def __init__(self):
        super().__init__()
        self.setWindowTitle("Clinic AI Chatbot")
        self.setGeometry(100, 100, 600, 500)
        self.conversation_history = []
        self.init_ui()
        initial_message = "Hello! I'm here to assist your doctor with the necessary details you provide here. What symptoms are you experiencing?"
        self.conversation_history.append({"role": "assistant", "content": initial_message})
        self.chat_history.append("AI: " + initial_message)

    def init_ui(self):
        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)


        self.chat_history = QTextEdit()
        self.chat_history.setReadOnly(True)
        layout.addWidget(self.chat_history)

        input_layout = QHBoxLayout()
        self.input_field = QLineEdit()
        input_layout.addWidget(self.input_field)


        self.send_button = QPushButton("Send")
        self.send_button.clicked.connect(self.send_message)
        input_layout.addWidget(self.send_button)

        self.extract_button = QPushButton("Extract")
        self.extract_button.clicked.connect(self.extract_report)
        input_layout.addWidget(self.extract_button)

        layout.addLayout(input_layout)

    def send_message(self):
        """Handle sending the user's message and getting an AI response."""
        user_text = self.input_field.text().strip()
        if user_text:
            self.chat_history.append("User: " + user_text)
            self.input_field.clear()
            ai_response = get_ai_response(self.conversation_history, user_text)
            self.chat_history.append("AI: " + ai_response)

    def extract_info_from_conversation(self):
        """
        Extracts patient responses for Symptoms, Duration, Severity, and Additional Info.
        Uses the order of user responses (ignoring greetings) as follows:
          - First response = Symptoms
          - Second response = Duration
          - Third response = Severity
          - Fourth response = Additional Info
        """
        user_responses = [
            msg["content"] for msg in self.conversation_history 
            if msg["role"] == "user" and msg["content"].lower() not in ["hello", "hi"]
        ]
        symptoms = user_responses[0] if len(user_responses) > 0 else "Not specified"
        duration = user_responses[1] if len(user_responses) > 1 else "Not specified"
        severity = user_responses[2] if len(user_responses) > 2 else "Not specified"
        additional_info = user_responses[3] if len(user_responses) > 3 else "Not specified"
        return symptoms, duration, severity, additional_info

    def extract_report(self):
        """
        When the extract button is pressed, ask for the patient's name,
        then generate a JSON file containing the full conversation,
        and generate a PDF report that includes:
          - Extracted Information (summarized from the JSON)
          - Chat Transcript (full conversation)
          - AI's Assumptions (a near diagnosis generated from the conversation JSON)
        """
        
        patient_name, ok = QInputDialog.getText(self, "Patient Name", "Enter Patient Name:")
        if not ok or not patient_name.strip():
            patient_name = "Unknown"

        
        symptoms_raw, duration_raw, severity_raw, additional_info_raw = self.extract_info_from_conversation()

        
        with open("conversation.json", "w") as json_file:
            json.dump(self.conversation_history, json_file, indent=2)

        
        summary = generate_summary(self.conversation_history)
        symptoms = summary.get("Symptoms", symptoms_raw)
        duration = summary.get("Duration", duration_raw)
        severity = summary.get("Severity", severity_raw)
        additional_info = summary.get("Additional Info", additional_info_raw)

        extracted_info = {
            "Patient Name": patient_name,
            "Symptoms": symptoms,
            "Duration": duration,
            "Severity": severity,
            "Additional Info": additional_info,
        }

        # Generate near diagnosis (AI's assumptions) using the conversation JSON.
        assumptions = generate_near_diagnosis(self.conversation_history)

        
        chat_transcript = self.chat_history.toPlainText()

        self.generate_pdf_report(extracted_info, chat_transcript, assumptions)

    def generate_pdf_report(self, extracted_info, chat_transcript, assumptions):
        pdf = FPDF()
        pdf.set_auto_page_break(auto=True, margin=15)
        pdf.add_page()

        pdf.set_font("Helvetica", "B", 16)
        pdf.cell(0, 10, "Clinic AI Chatbot Report", new_x=XPos.LMARGIN, new_y=YPos.NEXT, align="C")

        pdf.set_font("Helvetica", "", 12)
        for key, value in extracted_info.items():
            pdf.cell(0, 10, f"{key}: {value}", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "Chat Transcript:", new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.set_font("Helvetica", "", 10)
        max_width = pdf.w - 2 * pdf.l_margin  # Calculate available width

        # Add chat transcript line by line.
        for line in chat_transcript.split("\n"):
            clean_line = line.strip()
            if clean_line:
                pdf.multi_cell(max_width, 10, clean_line, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        # Leave a gap before AI's Assumptions.
        pdf.ln(5)
        pdf.set_font("Helvetica", "B", 14)
        pdf.cell(0, 10, "AI's Assumptions (Near Diagnosis):", new_x=XPos.LMARGIN, new_y=YPos.NEXT)
        pdf.set_font("Helvetica", "", 10)
        pdf.multi_cell(max_width, 10, assumptions, new_x=XPos.LMARGIN, new_y=YPos.NEXT)

        pdf.output("clinic_chatbot_report.pdf")

if __name__ == "__main__":
    app = QApplication(sys.argv)
    window = ChatWindow()
    window.show()
    sys.exit(app.exec())
