export default function Pagination({ page, pageCount, onChange }) {
  if (pageCount <= 1) return null;

  return (
    <div className="pagination">
      <button
        type="button"
        className="btn btn-ghost pagination-btn"
        onClick={() => onChange(page - 1)}
        disabled={page === 1}
      >
        Prev
      </button>

      <span className="pagination-status">
        Page {page} of {pageCount}
      </span>

      <button
        type="button"
        className="btn btn-ghost pagination-btn"
        onClick={() => onChange(page + 1)}
        disabled={page === pageCount}
      >
        Next
      </button>
    </div>
  );
}
