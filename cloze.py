import streamlit as st
from docx import Document
import nltk
from nltk import pos_tag, word_tokenize
from nltk.stem import WordNetLemmatizer
import random
import re

# ---------- NLTK data ----------
try:
    nltk.data.find("tokenizers/punkt")
except LookupError:
    nltk.download("punkt", quiet=True)

try:
    nltk.data.find("taggers/averaged_perceptron_tagger")
except LookupError:
    nltk.download("averaged_perceptron_tagger", quiet=True)

try:
    nltk.data.find("corpora/wordnet")
except LookupError:
    nltk.download("wordnet", quiet=True)

# ---------- 기본 설정 ----------
lemmatizer = WordNetLemmatizer()

VERB_TAGS = {"VB", "VBD", "VBG", "VBN", "VBP", "VBZ"}

TOKEN_CANDIDATE_RE = re.compile(r"[A-Za-z]+")

SEMANTIC_VERBS = [
    "eat",
    "sleep",
    "watch",
    "study",
    "run",
    "walk",
    "write",
    "read",
    "play",
    "buy",
    "love",
    "hate",
    "drink",
    "sing",
    "dance",
]


# ---------- 토큰 처리 ----------
def is_candidate_token(tok):
    return bool(TOKEN_CANDIDATE_RE.fullmatch(tok))


def tokenize_preserve_spacing(text):
    return word_tokenize(text)


def assemble_tokens(tokens):
    out = ""

    for i, t in enumerate(tokens):
        if i == 0:
            out += t
            continue

        if re.fullmatch(r"[^\w\s]", t):
            out += t
        else:
            out += " " + t

    return out


# ---------- 동사 형태 변형 ----------
def conjugate_verb(base, tag):

    if tag == "VB":
        return base

    if tag == "VBP":
        return base

    if tag == "VBZ":
        if base.endswith("y") and len(base) > 1:
            return base[:-1] + "ies"

        if base.endswith(("s", "x", "z", "ch", "sh")):
            return base + "es"

        return base + "s"

    if tag == "VBG":
        if base.endswith("e") and base != "be":
            return base[:-1] + "ing"

        return base + "ing"

    if tag == "VBD":
        if base.endswith("e"):
            return base + "d"

        return base + "ed"

    if tag == "VBN":
        if base.endswith("e"):
            return base + "d"

        return base + "ed"

    return base


# ---------- 문법형 보기 생성 ----------
def make_grammar_choices(word, tag):

    base = lemmatizer.lemmatize(word.lower(), "v")

    if tag == "VBZ":
        wrong = base

    elif tag == "VBD":
        wrong = base

    elif tag == "VBG":
        wrong = base

    elif tag == "VBN":
        wrong = base

    else:
        wrong = conjugate_verb(base, "VBZ")

    choices = [word, wrong]
    random.shuffle(choices)

    return choices, word


# ---------- 의미형 보기 생성 ----------
def make_semantic_choices(word, tag):

    base = lemmatizer.lemmatize(word.lower(), "v")

    wrong_base = random.choice(
        [v for v in SEMANTIC_VERBS if v != base]
    )

    wrong = conjugate_verb(wrong_base, tag)

    choices = [word, wrong]
    random.shuffle(choices)

    return choices, word


# ---------- 문제 생성 ----------
def generate_questions(file_like, quiz_mode, question_ratio):

    src = Document(file_like)

    question_paragraphs = []
    answer_map = {}

    next_num = 1

    for para in src.paragraphs:

        orig_text = para.text.strip()

        if not orig_text:
            question_paragraphs.append("")
            continue

        tokens = tokenize_preserve_spacing(orig_text)

        try:
            tagged = pos_tag(tokens)

        except Exception:
            tagged = [(t, "NN") for t in tokens]

        candidate_indices = []

        for i, (tok, tg) in enumerate(tagged):

            if tg in VERB_TAGS and is_candidate_token(tok):
                candidate_indices.append(i)

        n_candidates = len(candidate_indices)

        n_questions = max(
            1,
            int(round(n_candidates * question_ratio))
        )

        n_questions = min(n_questions, n_candidates)

        chosen = []

        if n_questions > 0:
            chosen = random.sample(candidate_indices, n_questions)

        out_tokens = list(tokens)

        for idx in sorted(chosen):

            original_word = tokens[idx]
            tag = tagged[idx][1]

            if quiz_mode == "문법형":
                choices, answer = make_grammar_choices(
                    original_word,
                    tag
                )

            else:
                choices, answer = make_semantic_choices(
                    original_word,
                    tag
                )

            display = (
                f"({next_num}) "
                f"{choices[0]} / {choices[1]}"
            )

            out_tokens[idx] = display

            answer_map[next_num] = {
                "answer": answer,
                "choices": choices
            }

            next_num += 1

        para_text = assemble_tokens(out_tokens)

        question_paragraphs.append(para_text)

    return question_paragraphs, answer_map


# ---------- 채점 ----------
def grade_answers(answer_map):

    total = len(answer_map)

    if total == 0:
        return 0, 0, []

    correct_count = 0

    results = []

    for num in sorted(answer_map.keys()):

        correct = answer_map[num]["answer"]

        user_ans = st.session_state.get(
            f"answer_{num}",
            ""
        )

        is_correct = (
            user_ans.strip().lower()
            == correct.strip().lower()
        )

        if is_correct:
            correct_count += 1

        results.append(
            {
                "num": num,
                "correct": correct,
                "user": user_ans,
                "is_correct": is_correct,
            }
        )

    return correct_count, total, results


# ---------- UI ----------
st.set_page_config(
    page_title="Grammar Choice Quiz",
    layout="wide"
)

st.title("📘 Grammar Choice Quiz")

st.markdown(
    """
Word(.docx) 파일에서 동사를 자동 추출하여
객관식 어법 문제를 생성합니다.
"""
)

st.markdown("---")

# 설정
quiz_mode = st.selectbox(
    "문제 유형 선택",
    ["문법형", "의미형"]
)

question_pct = st.slider(
    "문제 비율 (%)",
    min_value=10,
    max_value=100,
    value=30,
    step=10
)

uploaded_file = st.file_uploader(
    "Word(.docx) 파일 업로드",
    type=["docx"]
)

# 초기화
if st.button("🧹 초기화"):

    for key in list(st.session_state.keys()):
        del st.session_state[key]

    st.rerun()

# 문제 생성
if uploaded_file is not None:

    if st.button("📄 문제 만들기"):

        try:

            uploaded_file.seek(0)

            questions, answer_map = generate_questions(
                uploaded_file,
                quiz_mode,
                question_pct / 100.0
            )

            st.session_state["questions"] = questions
            st.session_state["answer_map"] = answer_map

            st.success("문제가 생성되었습니다.")

        except Exception as e:

            st.error("오류가 발생했습니다.")
            st.exception(e)

else:
    st.info("먼저 docx 파일을 업로드하세요.")

st.markdown("---")

# ---------- 문제지 ----------
with st.sidebar:

    st.header("📝 문제지")

    if "questions" in st.session_state:

        for para in st.session_state["questions"]:

            if para.strip() == "":
                st.write("")

            else:
                st.markdown(para)

    else:
        st.caption("문제지가 여기에 표시됩니다.")

# ---------- 답안 ----------
if "answer_map" in st.session_state:

    answer_map = st.session_state["answer_map"]

    st.subheader("✏️ 답 선택")

    for num in sorted(answer_map.keys()):

        info = answer_map[num]

        st.radio(
            f"{num}번",
            options=info["choices"],
            key=f"answer_{num}"
        )

    if st.button("✅ 채점하기"):

        correct_count, total, results = grade_answers(
            answer_map
        )

        score_pct = (
            correct_count / total * 100
            if total > 0 else 0
        )

        st.markdown("---")

        st.subheader("📊 결과")

        st.write(
            f"{total}문항 중 "
            f"**{correct_count}개 정답**"
        )

        st.write(
            f"점수: **{score_pct:.1f}점**"
        )

        for r in results:

            if r["is_correct"]:

                st.success(
                    f"{r['num']}번 정답"
                )

            else:

                st.error(
                    f"{r['num']}번 오답 "
                    f"(정답: {r['correct']})"
                )
