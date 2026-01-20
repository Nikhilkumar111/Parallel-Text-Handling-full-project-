"use client"

import AnswerCard from "./AnswerCard"

interface AnswerGridProps {
  results?: any[]
}

const AnswerGrid = ({ results = [] }: AnswerGridProps) => {
  if (!Array.isArray(results) || results.length === 0) return null

  return (
    <section className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
      {results.map((res: any, index: number) => (
        <AnswerCard key={res?.title ?? index} result={res} />
      ))}
    </section>
  )
}

export default AnswerGrid
