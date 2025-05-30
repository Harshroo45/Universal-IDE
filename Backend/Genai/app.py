import os
import re
import jwt
from google import genai
from dotenv import load_dotenv
from flask import Flask, request, jsonify, render_template
from flask_cors import CORS
from functools import wraps
from datetime import datetime, timezone
from prompts import *

valid_languages = {
    "python",
    "javascript",
    "rust",
    "mongodb",
    "swift",
    "ruby",
    "dart",
    "perl",
    "scala",
    "julia",
    "go",
    "java",
    "cpp",
    "csharp",
    "c",
    "sql",
    "typescript",
    "kotlin",
    "verilog",
}

app = Flask(__name__)

CORS(app)

try:
    load_dotenv()
except Exception as e:
    print(f"Error loading environment variables: {e}")

CODE_REGEX = r"```(?:\w+\n)?(.*?)```"

api_key = os.getenv("GEMINI_API_KEY")
gemini_model = os.getenv("GEMINI_MODEL")
gemini_model_1 = os.getenv("GEMINI_MODEL_1")
SECRET_KEY = os.getenv("JWT_SECRET")


def token_required(f):
    @wraps(f)
    def decorator(*args, **kwargs):
        token = None
        if "Authorization" in request.headers:
            auth_header = request.headers["Authorization"]
            if auth_header.startswith("Bearer "):
                token = auth_header.split(" ")[1]

        if not token:
            return jsonify({"message": "Token is missing!"}), 403

        try:
            decoded = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            request.user_data = decoded
        except jwt.InvalidTokenError as e:
            return jsonify({"message": "Invalid token!"}), 401

        return f(*args, **kwargs)

    return decorator


def get_generated_code(problem_description, language):
    try:
        if language not in valid_languages:
            return "Error: Unsupported language."

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=gemini_model,
            contents=generate_code_prompt.format(
                problem_description=problem_description, language=language
            ),
        )
        return response.text.strip()
    except Exception as e:
        return ""


def get_output(code, language):
    try:
        if language in languages_prompts:
            prompt = languages_prompts[language].format(
                code=code, time=utc_time_reference()
            )
        else:
            return "Error: Language not supported."

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=gemini_model,
            contents=prompt,
        )

        return response.text
    except Exception as e:
        return f"Error: Unable to process the code. {str(e)}"


def refactor_code(code, language, problem_description=None):
    try:
        if language not in valid_languages:
            return "Error: Unsupported language."

        client = genai.Client(api_key=api_key)

        if problem_description:
            refactor_contnet = refactor_code_prompt_user.format(
                code=code,
                language=language,
                problem_description=problem_description or "",
            )
        else:
            refactor_contnet = refactor_code_prompt.format(code=code, language=language)

        response = client.models.generate_content(
            model=gemini_model,
            contents=refactor_contnet,
        )

        return (
            response.text.strip()
            if hasattr(response, "text")
            else "Error: Invalid response format."
        )
    except Exception as e:
        print(f"Error analyzing code: {e}")
        return ""


def refactor_code_html_css_js(prompt, params, problem_description=None):
    try:

        if problem_description:
            formatted_prompt = prompt.format(
                **params, problem_description=problem_description
            )
        else:
            formatted_prompt = prompt.format(**params)

        client = genai.Client(api_key=api_key)

        response = client.models.generate_content(
            model=gemini_model_1,
            contents=formatted_prompt,
        )

        result = response.text.strip()
        return result
    except Exception as e:
        return f"Error: {e}"


def generate_html(prompt):
    formatted_prompt = html_prompt.format(prompt=prompt, time=utc_time_reference())

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=gemini_model_1,
        contents=formatted_prompt,
    )
    return extract_code(response.text)


def generate_css(html_content, project_description):
    formatted_prompt = css_prompt.format(
        html_content=html_content,
        project_description=project_description,
        time=utc_time_reference(),
    )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=gemini_model_1,
        contents=formatted_prompt,
    )

    return extract_code(response.text)


def generate_js(html_content, css_content, project_description):
    formatted_prompt = js_prompt.format(
        html_content=html_content,
        css_content=css_content,
        project_description=project_description,
        time=utc_time_reference(),
    )

    client = genai.Client(api_key=api_key)

    response = client.models.generate_content(
        model=gemini_model_1,
        contents=formatted_prompt,
    )

    return extract_code(response.text)


def utc_time_reference():
    return f"**Refer to this exact time: {datetime.now(timezone.utc).strftime('%I:%M %p on %B %d, %Y')} UTC**"


def extract_code(output):
    match = re.search(CODE_REGEX, output, re.DOTALL)
    if match:
        return match.group(1)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/generate_code", methods=["POST"])
@token_required
def generate_code():
    try:
        problem_description = request.json["problem_description"]
        language = request.json["language"]
        generated_code = get_generated_code(problem_description, language)
        return jsonify({"code": extract_code(generated_code)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/get-output", methods=["POST"])
def get_output_api():
    try:
        code = request.json["code"]
        language = request.json["language"]

        if not code or not language:
            return jsonify({"error": "Missing code or language"}), 400

        output = get_output(code, language)
        return jsonify({"output": output})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/refactor_code", methods=["POST"])
@token_required
def refactor_code_api():
    try:
        code = request.json["code"]
        language = request.json["language"]
        problem_description = request.json["problem_description"]

        if not code or not language:
            return jsonify({"error": "Missing code or language"}), 400

        if problem_description:
            refactored_code = refactor_code(code, language, problem_description)
        else:
            refactored_code = refactor_code(code, language)

        return jsonify({"code": extract_code(refactored_code)})
    except Exception as e:
        return jsonify({"error": str(e)}), 400


@app.route("/htmlcssjsgenerate-code", methods=["POST"])
@token_required
def htmlcssjs_generate():
    data = request.get_json()
    project_description = data.get("prompt")
    code_type = data.get("type")
    html_content = (
        data.get("htmlContent", "") if len(data.get("htmlContent", "")) > 0 else ""
    )
    css_content = (
        data.get("cssContent", "") if len(data.get("cssContent", "")) > 0 else ""
    )

    if not project_description:
        return jsonify({"error": "Project description is required"}), 400
        
    if not code_type or code_type not in ["html", "css", "js"]:
        return jsonify({"error": "Invalid or missing 'type' parameter"}), 400

    try:
        html_code = (
            generate_html(project_description) if code_type == "html" else html_content
        )
        css_code = (
            generate_css(html_code, project_description)
            if code_type == "css"
            else css_content
        )
        js_code = (
            generate_js(html_code, css_code, project_description)
            if code_type == "js"
            else ""
        )

        if code_type == "html":
            return jsonify({"html": html_code})
        elif code_type == "css":
            return jsonify({"css": css_code})
        elif code_type == "js":
            return jsonify({"js": js_code})
        else:
            return jsonify({"error": "Invalid code type requested."}), 400

    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"An unexpected error occurred: {str(e)}"}), 500


@app.route("/htmlcssjsrefactor-code", methods=["POST"])
@token_required
def htmlcssjs_refactor():
    try:
        data = request.get_json()
        html_content = data.get("html") if len(data.get("html", "")) > 0 else ""
        css_content = data.get("css") if len(data.get("css", "")) > 0 else ""
        js_content = data.get("js") if len(data.get("js", "")) > 0 else ""
        code_type = data.get("type")
        problem_description_raw = data.get("problem_description")
        problem_description = (
            problem_description_raw.strip().lower() if problem_description_raw else None
        )

        if not code_type:
            return jsonify({"error": "Type is required."}), 400

        if code_type == "html" and html_content and problem_description:
            html_content_refactored = refactor_code_html_css_js(
                refactor_html_prompt_user,
                {"html_content": html_content},
                problem_description,
            )
            html_content_refactored = re.search(
                CODE_REGEX, html_content_refactored, re.DOTALL
            )
            html_content_refactored = (
                html_content_refactored.group(1)
                if html_content_refactored
                else html_content
            )
            return jsonify({"html": html_content_refactored})

        elif code_type == "css" and html_content and problem_description:
            if not html_content:
                return (
                    jsonify({"error": "HTML content is required for CSS refactoring."}),
                    400,
                )
            css_content_refactored = refactor_code_html_css_js(
                refactor_css_prompt_user,
                {"html_content": html_content, "css_content": css_content},
                problem_description,
            )
            css_content_refactored = re.search(
                CODE_REGEX, css_content_refactored, re.DOTALL
            )
            css_content_refactored = (
                css_content_refactored.group(1)
                if css_content_refactored
                else css_content
            )
            return jsonify({"css": css_content_refactored})

        elif code_type == "js" and html_content and css_content and problem_description:
            if not html_content or not css_content:
                return (
                    jsonify(
                        {
                            "error": "Both HTML and CSS content are required for JS refactoring."
                        }
                    ),
                    400,
                )
            js_content_refactored = refactor_code_html_css_js(
                refactor_js_prompt_user,
                {
                    "html_content": html_content,
                    "css_content": css_content,
                    "js_content": js_content,
                },
                problem_description,
            )
            js_content_refactored = re.search(
                CODE_REGEX, js_content_refactored, re.DOTALL
            )
            js_content_refactored = (
                js_content_refactored.group(1) if js_content_refactored else js_content
            )

            return jsonify({"js": js_content_refactored})

        elif code_type == "html" and html_content:
            html_content_refactored = refactor_code_html_css_js(
                refactor_html_prompt, {"html_content": html_content}
            )
            html_content_refactored = re.search(
                CODE_REGEX, html_content_refactored, re.DOTALL
            )
            html_content_refactored = (
                html_content_refactored.group(1)
                if html_content_refactored
                else html_content
            )
            return jsonify({"html": html_content_refactored})

        elif code_type == "css" and html_content:
            if not html_content:
                return (
                    jsonify({"error": "HTML content is required for CSS refactoring."}),
                    400,
                )
            css_content_refactored = refactor_code_html_css_js(
                refactor_css_prompt,
                {"html_content": html_content, "css_content": css_content},
            )
            css_content_refactored = re.search(
                CODE_REGEX, css_content_refactored, re.DOTALL
            )
            css_content_refactored = (
                css_content_refactored.group(1)
                if css_content_refactored
                else css_content
            )
            return jsonify({"css": css_content_refactored})

        elif code_type == "js" and html_content and css_content:
            if not html_content or not css_content:
                return (
                    jsonify(
                        {
                            "error": "Both HTML and CSS content are required for JS refactoring."
                        }
                    ),
                    400,
                )
            js_content_refactored = refactor_code_html_css_js(
                refactor_js_prompt,
                {
                    "html_content": html_content,
                    "css_content": css_content,
                    "js_content": js_content,
                },
            )
            js_content_refactored = re.search(
                CODE_REGEX, js_content_refactored, re.DOTALL
            )
            js_content_refactored = (
                js_content_refactored.group(1) if js_content_refactored else js_content
            )
            return jsonify({"js": js_content_refactored})

        else:
            return (
                jsonify(
                    {
                        "error": "Please provide the appropriate content for the requested type."
                    }
                ),
                400,
            )

    except Exception as e:
        return jsonify({"error": f"An error occurred: {str(e)}"}), 500


if __name__ == "__main__":
    app.run(debug=False, port=5002)
