import { render, screen } from '@testing-library/react';
import { InlineMarkdown } from '@/components/dashboard/InlineMarkdown';

describe('InlineMarkdown', () => {
  it('renders plain text unchanged', () => {
    render(<InlineMarkdown text="Hello world" />);
    expect(screen.getByText('Hello world')).toBeInTheDocument();
  });

  it('renders **bold** as <strong>', () => {
    render(<InlineMarkdown text="This is **bold** text" />);
    const strong = screen.getByText('bold');
    expect(strong.tagName).toBe('STRONG');
  });

  it('renders *italic* as <em>', () => {
    render(<InlineMarkdown text="This is *italic* text" />);
    const em = screen.getByText('italic');
    expect(em.tagName).toBe('EM');
  });

  it('renders [link text](url) as the link text only — no <a> tag', () => {
    const { container } = render(
      <InlineMarkdown text="See [our website](https://example.com) for info" />,
    );
    // Link text renders as a raw text node (no wrapping element), so check textContent
    expect(container.textContent).toContain('our website');
    expect(document.querySelector('a')).toBeNull();
  });

  it('renders mixed bold, italic, and link in one string', () => {
    const { container } = render(
      <InlineMarkdown text="**Strong**, *em*, and [link](https://x.com)" />,
    );
    expect(screen.getByText('Strong').tagName).toBe('STRONG');
    expect(screen.getByText('em').tagName).toBe('EM');
    expect(container.textContent).toContain('link');
  });

  it('renders empty string without error', () => {
    const { container } = render(<InlineMarkdown text="" />);
    expect(container).toBeInTheDocument();
  });

  it('applies font-medium and text-text-primary classes to bold', () => {
    render(<InlineMarkdown text="**styled**" />);
    const strong = screen.getByText('styled');
    expect(strong).toHaveClass('font-medium', 'text-text-primary');
  });

  it('strips the link text and does not render the href', () => {
    render(<InlineMarkdown text="[click here](https://secret.com)" />);
    expect(screen.getByText('click here')).toBeInTheDocument();
    expect(document.querySelector('a')).toBeNull();
  });
});
