import React, { useMemo, useRef } from 'react';
import PhilosopherBadge from '@/components/effects/PhilosopherBadge';
import QuoteCard from '@/components/effects/QuoteCard';

const PHILOSOPHERS = ["Nietzsche", "Camus", "Socrates", "Plato", "Aristotle", "Marcus Aurelius"];
const PHILOSOPHERS_REGEX = new RegExp(`(${PHILOSOPHERS.join('|')})`, 'gi');

export function useStreamParser(text: string) {
  const stateRef = useRef({
    processedLength: 0,
    elements: [] as React.ReactNode[],
    foundPhilosophers: new Set<string>(),
    buffer: ""
  });

  return useMemo(() => {
    const state = stateRef.current;
    
    // Reset if text shrinks or completely changes (new message)
    if (text.length < state.processedLength || !text.startsWith(text.substring(0, state.processedLength))) {
      state.processedLength = 0;
      state.elements = [];
      state.foundPhilosophers.clear();
      state.buffer = "";
    }

    const newText = text.slice(state.processedLength);
    if (!newText && state.elements.length > 0 && !state.buffer) {
      return { elements: state.elements, hasDialecticSpark: state.foundPhilosophers.size > 1 };
    }

    state.buffer += newText;
    state.processedLength = text.length;

    // Detect philosophers (case-insensitive) in the new chunk
    PHILOSOPHERS.forEach(p => {
      if (new RegExp(p, 'i').test(newText)) {
        state.foundPhilosophers.add(p);
      }
    });

    let i = 0;
    while (i < state.buffer.length) {
      const quoteIdx = state.buffer.indexOf('"', i);
      if (quoteIdx === -1) {
        // No more quotes. Consume up to the last space to avoid cutting philosopher names.
        const lastSpaceIdx = state.buffer.lastIndexOf(' ');
        if (lastSpaceIdx > i) {
          const textChunk = state.buffer.substring(i, lastSpaceIdx + 1);
          processTextChunk(textChunk, state.elements, state.processedLength, i);
          i = lastSpaceIdx + 1;
        }
        break;
      } else {
        // Process text before the quote
        if (quoteIdx > i) {
          const textChunk = state.buffer.substring(i, quoteIdx);
          processTextChunk(textChunk, state.elements, state.processedLength, i);
        }
        
        // Find closing quote
        const endQuoteIdx = state.buffer.indexOf('"', quoteIdx + 1);
        if (endQuoteIdx === -1) {
          // Unmatched quote, wait for more chunks
          i = quoteIdx;
          break;
        } else {
          // Complete quote
          const quoteText = state.buffer.substring(quoteIdx + 1, endQuoteIdx);
          state.elements.push(<QuoteCard key={`quote-${state.processedLength}-${i}`} text={quoteText} author="Quoted Text" />);
          i = endQuoteIdx + 1;
        }
      }
    }
    
    // Keep unparsed text in the buffer for the next render
    state.buffer = state.buffer.substring(i);

    // Display elements = permanently parsed elements + anything left in the buffer (handled gracefully)
    const displayElements = [...state.elements];
    if (state.buffer) {
      // Process pending buffer on the fly without persisting it to state.elements yet
      const tempElements: React.ReactNode[] = [];
      processTextChunk(state.buffer, tempElements, state.processedLength, 'pending');
      displayElements.push(...tempElements);
    }

    return { 
      elements: displayElements, 
      hasDialecticSpark: state.foundPhilosophers.size > 1 
    };

  }, [text]);
}

function processTextChunk(text: string, elements: React.ReactNode[], lengthInfo: number, offset: number | string) {
  if (!text) return;
  const parts = text.split(PHILOSOPHERS_REGEX);
  parts.forEach((seg, i) => {
    if (!seg) return;
    const matchedPhil = PHILOSOPHERS.find(p => p.toLowerCase() === seg.toLowerCase());
    if (matchedPhil) {
      elements.push(<PhilosopherBadge key={`badge-${lengthInfo}-${offset}-${i}`} name={matchedPhil} />);
    } else {
      elements.push(<span key={`text-${lengthInfo}-${offset}-${i}`}>{seg}</span>);
    }
  });
}
