from fastapi import APIRouter, HTTPException, Depends
from db import supabase
from auth import get_current_user_and_company
from agents import run_all_agents
from llm import GeminiNarrator
from notify import notify_report_ready
import pandas as pd
import io

router = APIRouter()
narrator = GeminiNarrator()


@router.post("/analyze/{upload_id}")
async def analyze(upload_id: str, auth=Depends(get_current_user_and_company)):
    user, company_id = auth
    try:
        upload = supabase.table("uploads").select("*").eq("id", upload_id).execute()
        if not upload.data:
            raise HTTPException(status_code=404, detail="Upload not found")
        upload_data = upload.data[0]

        # the upload row only stores who uploaded it — resolve their
        # company and make sure it matches the caller's before touching it
        owner = supabase.table("users").select("company_id").eq("id", upload_data["uploaded_by"]).execute()
        if not owner.data or owner.data[0]["company_id"] != company_id:
            raise HTTPException(status_code=403, detail="You do not have access to this upload")

        storage_path = upload_data["storage_url"]

        report = supabase.table("reports").insert({
            "upload_id": upload_id,
            "company_id": company_id,
            "status": "processing"
        }).execute()
        report_id = report.data[0]["id"]

        file_bytes = supabase.storage.from_("uploads").download(storage_path)
        df = pd.read_csv(io.BytesIO(file_bytes))

        results = run_all_agents(df)
        ai_summary = narrator.summarize(results)

        update_payload = {
            "conservative": results["conservative"],
            "moderate": results["moderate"],
            "aggressive": results["aggressive"],
            "status": "complete",
        }
        if ai_summary:
            update_payload["ai_summary"] = ai_summary

        try:
            supabase.table("reports").update(update_payload).eq("id", report_id).execute()
        except Exception:
            # reports.ai_summary may not exist yet if the migration hasn't
            # been run — degrade gracefully instead of failing the whole analysis
            update_payload.pop("ai_summary", None)
            supabase.table("reports").update(update_payload).eq("id", report_id).execute()

        notify_report_ready(email=user.email, filename=upload_data["filename"], report_id=report_id)

        return {
            "report_id": report_id,
            "status": "complete",
            "results": results,
            "ai_summary": ai_summary,
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/reports/{report_id}")
async def get_report(report_id: str, auth=Depends(get_current_user_and_company)):
    user, company_id = auth
    try:
        report = supabase.table("reports").select("*").eq("id", report_id).execute()
        if not report.data:
            raise HTTPException(status_code=404, detail="Report not found")

        report_data = report.data[0]
        if report_data.get("company_id") != company_id:
            raise HTTPException(status_code=403, detail="You do not have access to this report")

        return report_data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
