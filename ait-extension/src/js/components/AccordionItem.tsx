import React, { useState, ReactNode } from 'react';
import { FiChevronDown, FiChevronRight } from 'react-icons/fi'; // Using existing icon library
import '../styles/Accordion.scss'; // We'll create this SCSS file

interface AccordionItemProps {
  title: string;
  children: ReactNode;
  startOpen?: boolean; // Optional prop to have an item open by default
}

const AccordionItem: React.FC<AccordionItemProps> = ({ title, children, startOpen = false }) => {
  const [isOpen, setIsOpen] = useState(startOpen);

  const toggleAccordion = () => {
    setIsOpen(!isOpen);
  };

  return (
    <div className={`accordion-item ${isOpen ? 'open' : ''}`}>
      <div className="accordion-header" onClick={toggleAccordion}>
        <span>{title}</span>
        <span className="accordion-icon">
          {isOpen ? <FiChevronDown /> : <FiChevronRight />}
        </span>
      </div>
      {isOpen && (
        <div className="accordion-content">
          {children}
        </div>
      )}
    </div>
  );
};

export default AccordionItem;
