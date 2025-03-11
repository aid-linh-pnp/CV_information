import streamlit as st
import requests
import fitz  # PyMuPDF
import json
from datetime import datetime
import tempfile

azure_api_key = st.secrets["azure"]["api_key"]
azure_endpoint = st.secrets["azure"]["endpoint"]
deployment_name = st.secrets["azure"]["deployment_name"]

# Đọc năm
current_year = datetime.now().year

# Hàm để đọc dữ liệu từ file PDF
def extract_text_from_pdf(uploaded_file):
    # Tạo một tệp tin tạm thời để lưu nội dung PDF tải lên
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(uploaded_file.read())  # Lưu nội dung vào tệp tin tạm thời
        temp_pdf_path = temp_file.name  # Đường dẫn đến tệp tin tạm thời

    # Mở file PDF và trích xuất nội dung
    document = fitz.open(temp_pdf_path)
    text = ""
    for page_num in range(document.page_count):
        page = document.load_page(page_num)
        text += page.get_text()  # Lấy văn bản từ trang
    return text

# Hàm gửi yêu cầu đến Azure OpenAI API
def call_openai_api(pdf_text, prompt):
    # Cấu hình yêu cầu HTTP cho Azure OpenAI với f-string để thay thế current_year vào đúng vị trí
    system_message = {
        "role": "system",
        "content": f"This year is {current_year}. Calculate age as the person's age when they left each company. If the CV does not include age, the age will be based on the candidate's first year of work minus 22 years old. If there are multiple jobs with overlapping dates, both jobs should be included with the same age calculated as the year when they left the job. Ensure that all freelancer jobs are included in the output. Add 1 year to the result to calculate the correct age."
    }

    # Tạo thông điệp yêu cầu OpenAI theo định dạng bạn yêu cầu
    user_message = {
        "role": "user", 
        "content": prompt
    }

    # Dữ liệu gửi yêu cầu
    request_data = {
        "messages": [system_message, user_message],
        "max_tokens": 16000,
        "temperature": 1,
        "top_p": 0.25
    }

    # Gửi yêu cầu đến Azure OpenAI (sử dụng api-key trong header thay vì Bearer token)
    headers = {
        'Content-Type': 'application/json',
        'api-key': azure_api_key  # Sử dụng api-key thay vì Bearer token
    }

    # Gửi yêu cầu POST đến OpenAI API
    response = requests.post(
        f"{azure_endpoint}/openai/deployments/{deployment_name}/chat/completions?api-version=2023-06-01-preview", 
        headers=headers, 
        data=json.dumps(request_data)
    )

    # Kiểm tra nếu có phản hồi thành công
    if response.status_code == 200:
        try:
            response_data = response.json()  # Thử parse JSON từ phản hồi
            
            # Lấy phần content từ phản hồi
            content = response_data['choices'][0]['message']['content'].strip()
            
            # Loại bỏ phần ```json và ``` xung quanh
            if content.startswith("```json"):
                content = content[7:].strip()  # Xóa dấu ```json từ đầu
            if content.endswith("```"):
                content = content[:-3].strip()  # Xóa dấu ``` ở cuối
            
            return content
        except json.JSONDecodeError:
            # Nếu không thể parse JSON, in thông báo lỗi
            print("Failed to decode JSON. Raw response:", response.text)
            st.error(f"Error decoding JSON: {response.text}")  # Hiển thị phản hồi raw trong giao diện Streamlit
            return "Error decoding response."
    else:
        # Nếu phản hồi không thành công, hiển thị mã lỗi và thông điệp lỗi
        print("Error Response:", response.text)  # Debug lỗi nếu có
        st.error(f"Error: {response.status_code} - {response.text}")
        return f"Error: {response.status_code} - {response.text}"

# Streamlit app
def main():
    st.title('CV Extractor and Age Calculator')

    # Hiển thị ô nhập file PDF
    uploaded_file = st.file_uploader("Upload CV PDF", type=["pdf"])

    # Hiển thị ô nhập nội dung prompt từ người dùng
    prompt_input = st.text_area("Enter Custom Prompt", value="""
Please extract the following information:
    - If the CV does not include the person's age, calculate the age as the person's first year of work minus 22 years old.
    - The age will be calculated as the year when the person left the job at the company, based on the tenure at each company. 
    - If the CV mentions multiple jobs with overlapping dates, **both jobs should be included**, with the same age calculated based on the year when the candidate left the job.
    - Ensure that all freelancer jobs are included in the output.
    - Tenure is month format.

Input Data: {pdf_text}

Required Output Format (just json):
{{
  "experience": # year of experience,
  "company": [
    {{
      "Company Name": {{
        "age": 27,
        "job_title": "Senior Mobile Developer",
        "Tenure": 24 
      }}
    }},
    {{
      "Company Name": {{
        "age": 25,
        "job_title": "Java Developer",
        "Tenure": 36
      }}
    }}...
  ]
}}
    """)

    # Nút Generate
    if st.button("Generate"):
        if uploaded_file is not None:
            # Lấy nội dung từ file PDF
            pdf_text = extract_text_from_pdf(uploaded_file)

            # Đưa nội dung file PDF vào trong prompt động
            prompt = prompt_input.format(pdf_text=pdf_text)  # Thay thế {pdf_text} bằng nội dung PDF

            # Gửi yêu cầu đến OpenAI API
            result = call_openai_api(pdf_text, prompt)

            # Hiển thị kết quả
            if result.startswith("Error"):
                st.error(result)  # Hiển thị lỗi nếu có
            else:
                try:
                    result_json = json.loads(result)
                    st.json(result_json, expanded=True)  # Hiển thị kết quả dưới dạng JSON
                except json.JSONDecodeError:
                    st.error(f"There was an error decoding the response: {result}")
                    st.write(result)  # Hiển thị phản hồi raw để bạn kiểm tra thêm
        else:
            st.error("Please upload a PDF file.")

if __name__ == "__main__":
    main()
