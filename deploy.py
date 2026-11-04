"""Deploy HireHub + Speak-to-Apply to Hugging Face Spaces.  Usage: python deploy.py path/to/keys.env"""
import secrets, sys
from pathlib import Path
from huggingface_hub import HfApi

env = dict(l.split("=", 1) for l in Path(sys.argv[1]).read_text().splitlines() if "=" in l and not l.startswith("#"))
env = {k.strip(): v.strip() for k, v in env.items()}
api = HfApi(token=env["HF_TOKEN"])
user = api.whoami()["name"]
root = Path(__file__).parent
state_file = root / "deploy_secrets.env"
state = dict(l.split("=", 1) for l in state_file.read_text().splitlines()) if state_file.exists() else {}
state.setdefault("PREFILL_SECRET", secrets.token_urlsafe(24))
state.setdefault("RECRUITER_PASSWORD", secrets.token_urlsafe(9))
state_file.write_text("\n".join(f"{k}={v}" for k, v in state.items()))

hh_id, sp_id = f"{user}/hirehub", f"{user}/speak-to-apply"
hh_url = f"https://{user.lower()}-hirehub.hf.space"
sp_url = f"https://{user.lower()}-speak-to-apply.hf.space"

def deploy(repo, folder, secrets_, variables):
    api.create_repo(repo, repo_type="space", space_sdk="docker", exist_ok=True)
    for k, v in secrets_.items():
        if v: api.add_space_secret(repo, k, v)
    for k, v in variables.items():
        api.add_space_variable(repo, k, v)
    api.upload_folder(repo_id=repo, repo_type="space", folder_path=str(root / folder),
                      ignore_patterns=["data/*", "__pycache__/*", "*.pyc", "make_jobs.py"])

deploy(hh_id, "hirehub", {k: env.get(k, "") for k in ["BREVO_API_KEY", "BREVO_SMTP_LOGIN", "BREVO_SMTP_KEY"]} |
       {"PREFILL_SECRET": state["PREFILL_SECRET"], "RECRUITER_PASSWORD": state["RECRUITER_PASSWORD"]},
       {"BREVO_SENDER_EMAIL": env.get("BREVO_SENDER_EMAIL", "")})
deploy(sp_id, "speak", {"GROQ_API_KEY": env["GROQ_API_KEY"], "PREFILL_SECRET": state["PREFILL_SECRET"]},
       {"HIREHUB_URL": hh_url})
print("HireHub:", hh_url, "\nSpeak-to-Apply:", sp_url, "\nRecruiter login: recruiter /", state["RECRUITER_PASSWORD"])
