import os, json, re, random, time
from groq import Groq

API_KEY = os.environ.get("GROQ_API_KEY")
MODEL_TEXT = "openai/gpt-oss-120b"   # for Aptitude, Reasoning, English
MODEL_NEWS = "groq/compound"         # has built-in web search, for Current Affairs
PER_CATEGORY = 20
BATCH = 10                           # questions per call (keeps tokens/minute low)
PAUSE = 10                           # seconds between calls (raise to 20 if you see 429 errors)
OUT_FILE = "questions.json"

client = Groq(api_key=API_KEY)

CATEGORIES = {
    "Current Affairs": (
        "Current Affairs for Indian competitive exams (SSC, Banking, APPSC/TSPSC, UPSC prelims level). "
        "Search the web and cover news from the last 30 days: national, international, economy, sports, "
        "awards, appointments, summits, schemes, science and technology. "
        "Questions must be factual and verifiable. Mention the date or context in the explanation."
    ),
    "Aptitude": (
        "Quantitative Aptitude: percentages, profit and loss, ratio, time and work, speed and distance, "
        "simple and compound interest, averages, number series, mensuration, data interpretation. "
        "Mostly medium and hard. Explanation must show the short calculation."
    ),
    "Logical Reasoning": (
        "Logical Reasoning: syllogisms, coding-decoding, blood relations, direction sense, seating "
        "arrangement, series, analogy, odd one out, statements and conclusions. "
        "Explanation must show the reasoning step by step."
    ),
    "English": (
        "English language: grammar, error spotting, fill in the blanks, synonyms, antonyms, "
        "idioms and phrases, one-word substitution, sentence improvement, vocabulary. "
        "Explanation must state the rule or meaning."
    ),
}


def build_prompt(category, desc, n, avoid):
    avoid_text = ""
    if avoid:
        avoid_text = "\nDo NOT repeat or rephrase these questions:\n- " + "\n- ".join(avoid[-30:])
    return f"""Generate exactly {n} unique multiple-choice questions.
Category: {category}
Focus: {desc}

Rules:
- Difficulty mix: about 50% medium, 40% hard, 10% easy. Shuffle the order.
- Exactly 4 options per question, all distinct and plausible.
- "correct" must be the exact text of one of the 4 options.
- Only one option can be correct.
- Any money amount must be in Indian Rupees written with the ₹ symbol (example: ₹5000). Never use $, USD or dollars unless a Current Affairs fact truly involves a foreign currency.
- Explanation: 1-2 sentences.
- Do not put letters like A) or B) in the options.
Return ONLY a JSON object of this form, with no other text:
{{"questions": [{{"question": "...", "options": ["...", "...", "...", "..."], "correct": "...", "explanation": "..."}}]}}{avoid_text}"""


def parse_json(text):
    text = re.sub(r"^```(?:json)?|```$", "", text.strip(), flags=re.M).strip()
    start, end = text.find("{"), text.rfind("}")
    data = json.loads(text[start:end + 1])
    return data["questions"] if isinstance(data, dict) else data


def call_model(category, prompt):
    if category == "Current Affairs":
        resp = client.chat.completions.create(
            model=MODEL_NEWS,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.6,
        )
    else:
        resp = client.chat.completions.create(
            model=MODEL_TEXT,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.9,
            response_format={"type": "json_object"},
            reasoning_effort="low",   # remove this line if your SDK/model rejects it
            max_tokens=4000,
        )
    return parse_json(resp.choices[0].message.content)


def fix_currency(text, category):
    if category == "Current Affairs":   # real USD facts must stay as they are
        return text
    text = re.sub(r"\$\s*", "₹", text)
    text = re.sub(r"\bRs\.?\s*(?=\d)", "₹", text)
    return text


def clean(item, category):
    opts = [fix_currency(str(o).strip(), category) for o in item.get("options", [])]
    correct = fix_currency(str(item.get("correct", "")).strip(), category)
    if len(opts) != 4 or len(set(o.lower() for o in opts)) != 4:
        return None
    if correct not in opts:
        match = [o for o in opts if o.lower() == correct.lower()]
        if not match:
            return None
        correct = match[0]
    random.shuffle(opts)
    return {
        "question": fix_currency(str(item["question"]).strip(), category),
        "optionOne": opts[0],
        "optionTwo": opts[1],
        "optionThree": opts[2],
        "optionFour": opts[3],
        "correctAns": correct,
        "explanation": fix_currency(str(item.get("explanation", "")).strip(), category),
        "category": category,
    }


def generate_category(category, desc, total):
    results, seen = [], set()
    attempts = 0
    while len(results) < total and attempts < 8:
        attempts += 1
        ask = min(BATCH, total - len(results) + 2)
        try:
            prompt = build_prompt(category, desc, ask, [r["question"] for r in results])
            raw = call_model(category, prompt)
        except Exception as e:
            msg = str(e)
            print(f"  [{category}] attempt {attempts} failed: {msg[:200]}")
            # wait long only when Groq reports a rate limit
            time.sleep(40 if ("429" in msg or "rate" in msg.lower()) else 5)
            continue
        for item in raw:
            q = clean(item, category)
            if q and q["question"].lower() not in seen:
                seen.add(q["question"].lower())
                results.append(q)
                if len(results) == total:
                    break
        print(f"  [{category}] {len(results)}/{total}")
        if len(results) < total:      # no pause after the last batch
            time.sleep(PAUSE)
    return results


def main():
    if not API_KEY:
        raise SystemExit("Set GROQ_API_KEY first.")
    all_questions = []
    for cat, desc in CATEGORIES.items():
        print(f"Generating {cat}...")
        all_questions.extend(generate_category(cat, desc, PER_CATEGORY))
    if len(all_questions) < 60:
        raise SystemExit(f"Only {len(all_questions)} questions generated, keeping old questions.json")
    with open(OUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_questions, f, ensure_ascii=False, indent=2)
    print(f"Saved {len(all_questions)} questions to {OUT_FILE}")


if __name__ == "__main__":
    main()
