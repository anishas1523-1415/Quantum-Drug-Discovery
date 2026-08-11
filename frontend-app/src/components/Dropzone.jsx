import { useRef, useState } from "react";

export default function Dropzone({ file, onFileSelected, disabled }) {
  const inputRef = useRef(null);
  const [dragging, setDragging] = useState(false);

  function handleFiles(fileList) {
    const picked = fileList?.[0];
    if (picked) onFileSelected(picked);
  }

  return (
    <div
      className={`dropzone glass-panel ${dragging ? "dropzone-active" : ""} ${disabled ? "dropzone-disabled" : ""}`}
      onClick={() => !disabled && inputRef.current?.click()}
      onDragOver={(e) => {
        e.preventDefault();
        if (!disabled) setDragging(true);
      }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragging(false);
        if (!disabled) handleFiles(e.dataTransfer.files);
      }}
      role="button"
      tabIndex={0}
    >
      <input
        ref={inputRef}
        type="file"
        accept=".csv"
        hidden
        disabled={disabled}
        onChange={(e) => handleFiles(e.target.files)}
      />

      <div className="dropzone-icon">
        <svg width="34" height="34" viewBox="0 0 24 24" fill="none">
          <path
            d="M12 16V4M12 4L7 9M12 4l5 5"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
            strokeLinejoin="round"
          />
          <path
            d="M4 16v2a2 2 0 002 2h12a2 2 0 002-2v-2"
            stroke="currentColor"
            strokeWidth="1.8"
            strokeLinecap="round"
          />
        </svg>
      </div>

      {file ? (
        <>
          <div className="dropzone-title">{file.name}</div>
          <div className="dropzone-subtitle">{(file.size / 1024).toFixed(1)} KB &middot; click or drop to replace</div>
        </>
      ) : (
        <>
          <div className="dropzone-title">Drop patient CSV here</div>
          <div className="dropzone-subtitle">or click to browse &middot; .csv files only</div>
        </>
      )}
    </div>
  );
}
