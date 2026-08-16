from fastapi import APIRouter, UploadFile, File, HTTPException, Depends
from db import supabase
from auth import get_current_user_and_company
import pandas as pd
import io
import time

router = APIRouter()

REQUIRED_COLUMNS = {"date", "revenue", "units_sold", "product", "region"}


def detect_columns(df: pd.DataFrame) -> dict:
    mapping = {}
    for col in df.columns:
        col_lower = col.lower().strip()
        if "date" in col_lower or "time" in col_lower:
            mapping["date"] = col
        elif "revenue" in col_lower or "sales" in col_lower or "amount" in col_lower:
            mapping["revenue"] = col
        elif "unit" in col_lower or "quantity" in col_lower or "qty" in col_lower:
            mapping["units_sold"] = col
        elif "product" in col_lower or "item" in col_lower or "sku" in col_lower:
            mapping["product"] = col
        elif "region" in col_lower or "location" in col_lower or "area" in col_lower:
            mapping["region"] = col
    return mapping


@router.post("/upload")
async def upload_file(
    file: UploadFile = File(...),
    auth=Depends(get_current_user_and_company),
):
    user, company_id = auth
    storage_path = None
    try:
        contents = await file.read()
        if not contents:
            raise HTTPException(status_code=400, detail="Uploaded file is empty")

        if file.filename.endswith(".csv"):
            df = pd.read_csv(io.BytesIO(contents))
        elif file.filename.endswith((".xlsx", ".xls")):
            df = pd.read_excel(io.BytesIO(contents))
        else:
            raise HTTPException(status_code=400, detail="Only CSV and Excel files are supported")

        if df.empty:
            raise HTTPException(status_code=400, detail="File contains no rows")

        col_mapping = detect_columns(df)
        missing = REQUIRED_COLUMNS - set(col_mapping.keys())

        if missing:
            return {
                "status": "warning",
                "message": f"Could not detect columns: {sorted(missing)}. Please check your file.",
                "detected_columns": col_mapping,
                "your_columns": list(df.columns)
            }

        df = df.rename(columns={v: k for k, v in col_mapping.items()})

        try:
            pd.to_datetime(df["date"])
            pd.to_numeric(df["revenue"])
            pd.to_numeric(df["units_sold"])
        except Exception:
            raise HTTPException(
                status_code=400,
                detail="Could not parse the date/revenue/units_sold columns — check for missing or non-numeric values"
            )

        storage_path = f"{user.id}/{int(time.time())}_{file.filename}"
        supabase.storage.from_("uploads").upload(
            path=storage_path,
            file=contents,
            file_options={"content-type": "text/csv"}
        )

        try:
            upload_record = supabase.table("uploads").insert({
                "filename": file.filename,
                "row_count": len(df),
                "uploaded_by": user.id,
                "storage_url": storage_path
            }).execute()
        except Exception:
            # don't leave an orphaned file in storage if the DB insert fails
            supabase.storage.from_("uploads").remove([storage_path])
            raise

        upload_id = upload_record.data[0]["id"]

        return {
            "status": "success",
            "upload_id": upload_id,
            "filename": file.filename,
            "rows": len(df),
            "columns_detected": col_mapping,
            "preview": df.head(3).to_dict(orient="records")
        }

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/list")
async def list_uploads(auth=Depends(get_current_user_and_company)):
    user, company_id = auth
    try:
        teammates = supabase.table("users").select("id").eq("company_id", company_id).execute()
        teammate_ids = [row["id"] for row in teammates.data] or [user.id]

        uploads = (
            supabase.table("uploads")
            .select("*")
            .in_("uploaded_by", teammate_ids)
            .order("uploaded_at", desc=True)
            .execute()
        )
        return uploads.data

    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
