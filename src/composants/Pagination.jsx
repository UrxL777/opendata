// ═══ LES NUMÉROS DE PAGE, sous le catalogue et la galerie des dashboards ═══

// Pagination partagée par le catalogue de données et la galerie des dashboards
export default function Pagination({ pageCourante, totalPages, onChanger }) {
  if (totalPages <= 1) return null

  const pages = []
  for (let i = 1; i <= totalPages; i++) pages.push(i)

  return (
    <div className="flex justify-center items-center gap-1 mt-8 flex-wrap">
      <button
        onClick={() => onChanger(pageCourante - 1)}
        disabled={pageCourante === 1}
        className="px-3 py-2 text-sm rounded-lg border border-bordure text-texte-secondaire hover:bg-fond-doux disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Précédent
      </button>
      {pages.map(p => (
        <button
          key={p}
          onClick={() => onChanger(p)}
          className={`w-9 h-9 text-sm rounded-lg border ${
            p === pageCourante
              ? 'bg-principal text-texte-inverse border-principal'
              : 'border-bordure text-texte-secondaire hover:bg-fond-doux'
          }`}
        >
          {p}
        </button>
      ))}
      <button
        onClick={() => onChanger(pageCourante + 1)}
        disabled={pageCourante === totalPages}
        className="px-3 py-2 text-sm rounded-lg border border-bordure text-texte-secondaire hover:bg-fond-doux disabled:opacity-40 disabled:cursor-not-allowed"
      >
        Suivant
      </button>
    </div>
  )
}
