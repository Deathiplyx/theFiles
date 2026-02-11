from flask import Flask, request, jsonify
from flask_cors import CORS
import sqlite3
from collections import defaultdict

DB_FILE = "epstein_index.db"
SAMPLE_LIMIT = 3

app = Flask(__name__)
CORS(app)

def highlight_phrase(text, phrase):
    lower_text = text.lower()
    result = ""
    i = 0

    while True:
        idx = lower_text.find(phrase, i)
        if idx == -1:
            result += text[i:]
            break

        result += text[i:idx]
        result += "[" + text[idx:idx+len(phrase)] + "]"
        i = idx + len(phrase)

    return result


def extract_context(text, index, phrase, window=120):
    start = text.rfind('.', 0, index)
    end = text.find('.', index)

    if start != -1 and end != -1 and (end - start) < 400:
        start += 1
        sentence = text[start:end+1].strip()
        if len(sentence) > 20:
            return highlight_phrase(sentence, phrase)

    start = max(0, index - window)
    end = min(len(text), index + window)
    snippet = text[start:end].replace("\n", " ").strip()

    return highlight_phrase("... " + snippet + " ...", phrase)


@app.route("/search")
def search():
    phrase = request.args.get("q", "").lower().strip()
    mode = request.args.get("mode", "sample")

    if not phrase:
        return jsonify({"error": "No query"}), 400

    show_all = mode == "all"
    show_sample = mode == "sample"

    conn = sqlite3.connect(DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT file, page, content FROM pages")

    file_counts = defaultdict(int)
    file_samples = defaultdict(list)

    for file, page, content in cur:
        text_lower = content.lower()
        pos = 0

        while True:
            idx = text_lower.find(phrase, pos)
            if idx == -1:
                break

            file_counts[file] += 1

            if show_all:
                file_samples[file].append((page, content, idx))
            elif show_sample and len(file_samples[file]) < SAMPLE_LIMIT:
                file_samples[file].append((page, content, idx))

            pos = idx + len(phrase)

    conn.close()

    total = sum(file_counts.values())

    results = []
    sorted_files = sorted(file_counts.items(), key=lambda x: x[1], reverse=True)

    for file, count in sorted_files:
        entry = {
            "file": file,
            "count": count,
            "samples": []
        }

        if show_all or show_sample:
            for page, content, idx in file_samples[file]:
                context = extract_context(content, idx, phrase)
                entry["samples"].append({
                    "page": page,
                    "context": context
                })

        results.append(entry)

    return jsonify({
        "total": total,
        "results": results
    })


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=10000)
