import type { DocSummary } from "../../types/api";
import { Link } from "react-router-dom";

export function BookCard({ doc }: { doc: DocSummary }) {
  return (
    <Link to={`/users/read/${doc.id}`} className="book-card">
      {doc.first_page_image_url ? (
        <img src={doc.first_page_image_url} alt="" className="book-card-image" />
      ) : (
        <div className="book-card-placeholder" />
      )}
      <div className="book-card-body">
        <h2>{doc.title}</h2>
        <p className="book-card-meta">{doc.pages_number} pages · {doc.ext}</p>
        {doc.first_page_content && (
          <p className="book-card-preview arabic-text" dir="auto">
            {doc.first_page_content}
          </p>
        )}
      </div>
    </Link>
  );
}
