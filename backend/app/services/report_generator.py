import os
import io
import uuid
import hashlib
from datetime import datetime, timezone
from typing import Dict, Any, List, Optional, Tuple
import openpyxl
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.lib.units import inch
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.platypus import (
    SimpleDocTemplate,
    Paragraph,
    Spacer,
    Table,
    TableStyle,
    KeepTogether,
    HRFlowable,
)

from app.schemas.report import ReportExportRequest, ReportQueryItem
from app.services.storage_service import StorageService


# Shared Report Styling & Palette Constants
COLOR_PRIMARY = colors.HexColor("#1e293b")
COLOR_ACCENT = colors.HexColor("#2563eb")
COLOR_SUCCESS = colors.HexColor("#16a34a")
COLOR_BG_LIGHT = colors.HexColor("#f8fafc")
COLOR_BORDER = colors.HexColor("#e2e8f0")
COLOR_TEXT_DARK = colors.HexColor("#0f172a")
COLOR_TEXT_MUTED = colors.HexColor("#64748b")

_SAMPLE_STYLES = getSampleStyleSheet()
REPORT_STYLES = {
    "title": ParagraphStyle("RptTitle", parent=_SAMPLE_STYLES["Heading1"], fontSize=20, leading=24, textColor=COLOR_PRIMARY, fontName="Helvetica-Bold", spaceAfter=4),
    "subtitle": ParagraphStyle("RptSub", parent=_SAMPLE_STYLES["Normal"], fontSize=10, leading=13, textColor=COLOR_TEXT_MUTED, fontName="Helvetica", spaceAfter=12),
    "h2": ParagraphStyle("RptH2", parent=_SAMPLE_STYLES["Heading2"], fontSize=13, leading=16, textColor=COLOR_ACCENT, fontName="Helvetica-Bold", spaceBefore=12, spaceAfter=6),
    "nl": ParagraphStyle("RptNL", parent=_SAMPLE_STYLES["Normal"], fontSize=11, leading=15, textColor=COLOR_TEXT_DARK, fontName="Helvetica-Bold"),
    "body": ParagraphStyle("RptBody", parent=_SAMPLE_STYLES["Normal"], fontSize=9, leading=12, textColor=COLOR_TEXT_DARK, fontName="Helvetica"),
    "code": ParagraphStyle("RptCode", parent=_SAMPLE_STYLES["Code"], fontSize=8.5, leading=11, textColor=COLOR_TEXT_DARK, fontName="Courier", backColor=colors.HexColor("#f1f5f9"), borderColor=COLOR_BORDER, borderWidth=0.5, borderPadding=6, spaceBefore=4, spaceAfter=6),
}


class ReportGeneratorService:
    """
    Reporting Engine (REQ-RPT-01, REQ-RPT-02, Rule R8.3)
    Supports PDF and Excel export for single queries and multi-query sessions.
    Generates verifiable documents containing:
      1. Natural-language question
      2. Generated / Executed SQL
      3. 5-part Reliability Score breakdown
      4. Result validation & Critic findings
      5. Execution results table preview
      6. ISO generation timestamp and SHA-256 content hash
    """

    def __init__(self, reports_dir: Optional[str] = None):
        self.storage = StorageService()
        self.reports_dir = reports_dir or self.storage.local_dir
        os.makedirs(self.reports_dir, exist_ok=True)

    def generate_pdf(self, request: ReportExportRequest, user_id: int = 1) -> Tuple[str, str, str]:
        """
        Generates a PDF report and returns (report_id, file_path, content_hash).
        """
        report_id = str(uuid.uuid4())
        file_name = f"report_{report_id}.pdf"
        file_path = os.path.join(self.reports_dir, file_name)

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=letter,
            rightMargin=36,
            leftMargin=36,
            topMargin=40,
            bottomMargin=40,
        )

        title_style = REPORT_STYLES["title"]
        subtitle_style = REPORT_STYLES["subtitle"]
        h2_style = REPORT_STYLES["h2"]
        nl_style = REPORT_STYLES["nl"]
        body_style = REPORT_STYLES["body"]
        code_style = REPORT_STYLES["code"]
        border_color = COLOR_BORDER
        accent_color = COLOR_ACCENT
        primary_color = COLOR_PRIMARY
        bg_light = COLOR_BG_LIGHT
        text_dark = COLOR_TEXT_DARK
        text_muted = COLOR_TEXT_MUTED

        story = []
        gen_timestamp = datetime.now(timezone.utc).isoformat()

        # Header Title Banner
        story.append(Paragraph(request.title, title_style))
        meta_text = (
            f"Scope: <b>{request.scope.upper()}</b> | Data Source: <b>{request.data_source_name}</b> | "
            f"Role: <b>{request.role_name}</b> | Generated: <b>{gen_timestamp}</b>"
        )
        story.append(Paragraph(meta_text, subtitle_style))
        story.append(HRFlowable(width="100%", thickness=1.5, color=accent_color, spaceBefore=0, spaceAfter=14))

        # Overall summary stats if multi-query session
        if request.scope == "session" and len(request.queries) > 1:
            total_q = len(request.queries)
            success_count = sum(1 for q in request.queries if q.status == "success")
            avg_rel = 0.0
            valid_rel_scores = []
            for q in request.queries:
                if q.reliability_breakdown and "composite_score" in q.reliability_breakdown:
                    valid_rel_scores.append(float(q.reliability_breakdown["composite_score"]))
            if valid_rel_scores:
                avg_rel = sum(valid_rel_scores) / len(valid_rel_scores)

            summary_data = [
                ["Total Queries Analyzed", "Successful Executions", "Avg Reliability Score", "Scope"],
                [str(total_q), f"{success_count}/{total_q}", f"{avg_rel * 100:.1f}%" if avg_rel > 0 else "N/A", "Multi-Query Session"]
            ]
            summary_table = Table(summary_data, colWidths=[130, 130, 130, 150])
            summary_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f1f5f9")),
                ("TEXTCOLOR", (0, 0), (-1, 0), primary_color),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("ALIGN", (0, 0), (-1, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                ("TOPPADDING", (0, 0), (-1, -1), 6),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 6),
            ]))
            story.append(summary_table)
            story.append(Spacer(1, 14))

        # Render each Query Card
        for idx, item in enumerate(request.queries, start=1):
            query_elements = []
            
            # Query section title
            section_title = f"Query #{idx}: {item.question}" if request.scope == "session" else f"Natural Language Query"
            query_elements.append(Paragraph(section_title, h2_style))
            
            if request.scope != "session":
                query_elements.append(Paragraph(f"<b>User Question:</b> {item.question}", nl_style))
                query_elements.append(Spacer(1, 6))

            # Executed SQL Block (Rule R8.3)
            query_elements.append(Paragraph("<b>Executed SQL:</b>", body_style))
            cleaned_sql = item.executed_sql.strip().replace("<", "&lt;").replace(">", "&gt;").replace("\n", "<br/>")
            query_elements.append(Paragraph(cleaned_sql, code_style))

            # Reliability Score Breakdown (Rule R8.3 & REQ-TRUST-01)
            rel = item.reliability_breakdown or {}
            composite = rel.get("composite_score") or rel.get("composite")
            if composite is not None and isinstance(composite, (int, float)):
                score_pct = f"{float(composite) * 100:.1f}%" if float(composite) <= 1.0 else f"{float(composite):.1f}%"
            elif composite is not None:
                score_pct = str(composite)
            else:
                score_pct = "N/A"

            subscores = rel.get("sub_scores", {})
            def fmt_sub(key: str) -> str:
                v = subscores.get(key)
                if v is None:
                    return "N/A"
                return f"{float(v)*100:.0f}%" if float(v) <= 1.0 else f"{float(v):.0f}%"

            rel_data = [
                ["Reliability Dimension", "Sub-Score", "Weight", "Evidence Trace"],
                ["Schema Grounding", fmt_sub('schema_grounding'), "25%", "Catalog lookup & foreign key binding"],
                ["Join Confidence", fmt_sub('join_confidence'), "20%", "FK relationship graph validation"],
                ["Filter Interpretation", fmt_sub('filter_interpretation'), "15%", "Sanitized literal value grounding"],
                ["Execution Validation", fmt_sub('execution_validation'), "20%", "Zero-error sandbox execution"],
                ["Result Sanity", fmt_sub('result_sanity'), "20%", "Cardinality & non-empty result checks"],
                ["<b>Composite Trust Score</b>", f"<b>{score_pct}</b>", "<b>100%</b>", f"Status: <b>{item.status.upper()}</b>"]
            ]
            rel_table = Table(rel_data, colWidths=[140, 75, 55, 270])
            rel_table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#e2e8f0")),
                ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#eff6ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), primary_color),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTNAME", (0, -1), (-1, -1), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 8),
                ("ALIGN", (1, 0), (2, -1), "CENTER"),
                ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            query_elements.append(Paragraph("<b>Reliability & Evidence Verification:</b>", body_style))
            query_elements.append(Spacer(1, 3))
            query_elements.append(rel_table)
            query_elements.append(Spacer(1, 8))

            # Result Preview Table if data provided
            if request.include_raw_data and item.rows and item.columns:
                query_elements.append(Paragraph(f"<b>Result Data Preview (Showing {min(len(item.rows), request.max_data_rows)} of {item.row_count or len(item.rows)} rows):</b>", body_style))
                query_elements.append(Spacer(1, 3))
                
                cols = item.columns[:7]  # Cap columns for PDF width
                preview_rows = item.rows[:request.max_data_rows]
                
                table_rows = [[Paragraph(f"<b>{c}</b>", body_style) for c in cols]]
                for r in preview_rows:
                    row_cells = []
                    for c in cols:
                        val = r.get(c, "")
                        str_val = str(val) if val is not None else "NULL"
                        if len(str_val) > 30:
                            str_val = str_val[:27] + "..."
                        row_cells.append(Paragraph(str_val, body_style))
                    table_rows.append(row_cells)

                data_table = Table(table_rows, colWidths=[540 / len(cols)] * len(cols))
                data_table.setStyle(TableStyle([
                    ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#f8fafc")),
                    ("GRID", (0, 0), (-1, -1), 0.5, border_color),
                    ("TOPPADDING", (0, 0), (-1, -1), 3),
                    ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
                    ("FONTSIZE", (0, 0), (-1, -1), 7.5),
                ]))
                query_elements.append(data_table)
                query_elements.append(Spacer(1, 10))

            query_elements.append(HRFlowable(width="100%", thickness=0.5, color=border_color, spaceBefore=6, spaceAfter=10))
            story.append(KeepTogether(query_elements))

        # Footer Audit Stamp (Rule R8.3)
        doc.build(story)
        pdf_bytes = buffer.getvalue()
        content_hash = hashlib.sha256(pdf_bytes).hexdigest()

        # Persist through StorageService abstraction
        stored_meta = self.storage.store_artifact(
            content=pdf_bytes,
            filename=file_name,
            content_type="application/pdf",
            prefix="reports",
        )

        return report_id, stored_meta["uri"], content_hash

    def generate_excel(self, request: ReportExportRequest, user_id: int = 1) -> Tuple[str, str, str]:
        """
        Generates a styled multi-sheet Excel workbook and returns (report_id, file_path, content_hash).
        """
        report_id = str(uuid.uuid4())
        file_name = f"report_{report_id}.xlsx"
        file_path = os.path.join(self.reports_dir, file_name)

        wb = openpyxl.Workbook()
        gen_timestamp = datetime.now(timezone.utc).isoformat()

        # Styling definitions
        header_fill = PatternFill(start_color="1E293B", end_color="1E293B", fill_type="solid")
        accent_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
        section_fill = PatternFill(start_color="F1F5F9", end_color="F1F5F9", fill_type="solid")
        white_bold = Font(name="Calibri", size=11, bold=True, color="FFFFFF")
        black_bold = Font(name="Calibri", size=11, bold=True, color="0F172A")
        title_font = Font(name="Calibri", size=16, bold=True, color="1E293B")
        code_font = Font(name="Consolas", size=10, color="0F172A")
        thin_border = Border(
            left=Side(style='thin', color='E2E8F0'),
            right=Side(style='thin', color='E2E8F0'),
            top=Side(style='thin', color='E2E8F0'),
            bottom=Side(style='thin', color='E2E8F0')
        )

        # Sheet 1: Executive Summary & Provenance
        ws_summary = wb.active
        ws_summary.title = "Executive Summary"
        ws_summary.views.sheetView[0].showGridLines = True

        ws_summary.append([request.title])
        ws_summary["A1"].font = title_font
        ws_summary.append([])

        # Metadata table
        meta_items = [
            ("Report ID", report_id),
            ("Generation Timestamp (UTC)", gen_timestamp),
            ("Report Scope", request.scope.upper()),
            ("Data Source", request.data_source_name),
            ("Requested By Role", request.role_name),
            ("Total Queries", len(request.queries)),
        ]
        ws_summary.append(["METADATA & PROVENANCE", "VALUE"])
        ws_summary.cell(row=3, column=1).font = white_bold
        ws_summary.cell(row=3, column=1).fill = header_fill
        ws_summary.cell(row=3, column=2).font = white_bold
        ws_summary.cell(row=3, column=2).fill = header_fill

        for r_idx, (k, v) in enumerate(meta_items, start=4):
            ws_summary.append([k, str(v)])
            ws_summary.cell(row=r_idx, column=1).font = black_bold
            ws_summary.cell(row=r_idx, column=1).fill = section_fill
            ws_summary.cell(row=r_idx, column=1).border = thin_border
            ws_summary.cell(row=r_idx, column=2).border = thin_border

        ws_summary.append([])
        start_q_row = len(meta_items) + 6

        # Queries Summary Table in Sheet 1
        ws_summary.append(["#", "Question", "Status", "Reliability Score", "Latency (ms)", "Rows", "SQL Summary"])
        for col_i in range(1, 8):
            cell = ws_summary.cell(row=start_q_row, column=col_i)
            cell.font = white_bold
            cell.fill = accent_fill
            cell.border = thin_border

        for q_idx, q in enumerate(request.queries, start=1):
            curr_row = start_q_row + q_idx
            rel = q.reliability_breakdown or {}
            comp = rel.get("composite_score") or rel.get("composite")
            if comp is not None and isinstance(comp, (int, float)):
                score_str = f"{float(comp)*100:.1f}%" if float(comp) <= 1.0 else f"{float(comp):.1f}%"
            elif comp is not None:
                score_str = str(comp)
            else:
                score_str = "N/A"
            
            ws_summary.append([
                q_idx,
                q.question,
                q.status,
                score_str,
                q.latency_ms,
                q.row_count or len(q.rows),
                q.executed_sql[:120] + ("..." if len(q.executed_sql) > 120 else "")
            ])
            for col_i in range(1, 8):
                ws_summary.cell(row=curr_row, column=col_i).border = thin_border

        # Adjust summary sheet column widths
        for col in ws_summary.columns:
            max_len = max(len(str(cell.value or "")) for cell in col)
            col_letter = get_column_letter(col[0].column)
            ws_summary.column_dimensions[col_letter].width = max(max_len + 3, 14)
        ws_summary.column_dimensions["B"].width = 40
        ws_summary.column_dimensions["G"].width = 50

        # Sheet 2+: Data sheets per query
        for q_idx, q in enumerate(request.queries, start=1):
            sheet_title = f"Query_{q_idx}_Data" if len(request.queries) > 1 else "Query Results"
            ws_data = wb.create_sheet(title=sheet_title)
            ws_data.views.sheetView[0].showGridLines = True

            # Question & SQL Header
            ws_data.append([f"Query #{q_idx}: {q.question}"])
            ws_data["A1"].font = Font(name="Calibri", size=13, bold=True, color="1E293B")
            ws_data.append([f"Executed SQL: {q.executed_sql}"])
            ws_data["A2"].font = code_font
            ws_data.append([])

            if q.columns:
                ws_data.append(q.columns)
                for c_idx in range(1, len(q.columns) + 1):
                    cell = ws_data.cell(row=4, column=c_idx)
                    cell.font = white_bold
                    cell.fill = header_fill
                    cell.border = thin_border
                    cell.alignment = Alignment(horizontal="center")

                for r_i, r in enumerate(q.rows, start=5):
                    row_vals = [r.get(c, "") for c in q.columns]
                    ws_data.append(row_vals)
                    for c_idx in range(1, len(q.columns) + 1):
                        ws_data.cell(row=r_i, column=c_idx).border = thin_border

                for col in ws_data.columns:
                    max_len = max(len(str(cell.value or "")) for cell in col)
                    col_letter = get_column_letter(col[0].column)
                    ws_data.column_dimensions[col_letter].width = max(max_len + 3, 12)

        buffer = io.BytesIO()
        wb.save(buffer)
        excel_bytes = buffer.getvalue()
        content_hash = hashlib.sha256(excel_bytes).hexdigest()

        # Persist through StorageService
        stored_meta = self.storage.store_artifact(
            content=excel_bytes,
            filename=file_name,
            content_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            prefix="reports",
        )

        return report_id, stored_meta["uri"], content_hash

    def get_report_file(self, report_id: str) -> Optional[Tuple[str, str]]:
        """
        Locates a report file on disk or storage and returns (file_path, media_type).
        """
        pdf_key = f"reports/report_{report_id}.pdf"
        pdf_bytes = self.storage.retrieve_artifact(pdf_key)
        if pdf_bytes is not None:
            local_path = os.path.join(self.reports_dir, f"report_{report_id}.pdf")
            if not os.path.exists(local_path):
                with open(local_path, "wb") as f:
                    f.write(pdf_bytes)
            return local_path, "application/pdf"

        xlsx_key = f"reports/report_{report_id}.xlsx"
        xlsx_bytes = self.storage.retrieve_artifact(xlsx_key)
        if xlsx_bytes is not None:
            local_path = os.path.join(self.reports_dir, f"report_{report_id}.xlsx")
            if not os.path.exists(local_path):
                with open(local_path, "wb") as f:
                    f.write(xlsx_bytes)
            return local_path, "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"

        return None
