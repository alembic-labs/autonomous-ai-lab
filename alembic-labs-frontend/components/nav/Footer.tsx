import Link from "next/link";
import { Wordmark } from "./Wordmark";

export function Footer() {
  return (
    <footer className="mt-24 border-t border-border-subtle">
      <div className="container-content py-10 grid grid-cols-1 md:grid-cols-3 gap-8">
        <div>
          <Wordmark size="lg" />
          <p className="mt-3 text-text-secondary text-small">peptides, distilled.</p>
          <p className="mt-1 text-text-muted text-small">
            autonomous in silico research
          </p>
        </div>

        <div>
          <h3 className="text-text-muted text-small uppercase tracking-wider mb-3">
            navigate
          </h3>
          <ul className="space-y-1.5 text-small">
            <li>
              <Link href="/folds" className="text-text-secondary hover:text-brand">
                folds
              </Link>
            </li>
            <li>
              <Link href="/lab" className="text-text-secondary hover:text-brand">
                lab
              </Link>
            </li>
            <li>
              <Link href="/stack" className="text-text-secondary hover:text-brand">
                stack analyzer
              </Link>
            </li>
            <li>
              <Link href="/about" className="text-text-secondary hover:text-brand">
                about
              </Link>
            </li>
          </ul>
        </div>

        <div>
          <h3 className="text-text-muted text-small uppercase tracking-wider mb-3">
            elsewhere
          </h3>
          <ul className="space-y-1.5 text-small">
            <li>
              <a
                href="https://twitter.com/alembiclabs"
                target="_blank"
                rel="noreferrer"
                className="text-text-secondary hover:text-brand"
              >
                twitter / @alembiclabs ↗
              </a>
            </li>
            <li>
              <a
                href="https://github.com/alembic-labs"
                target="_blank"
                rel="noreferrer"
                className="text-text-secondary hover:text-brand"
              >
                github / alembic-labs ↗
              </a>
            </li>
            <li>
              <a
                href="mailto:contact@alembic.bio"
                className="text-text-secondary hover:text-brand"
              >
                contact@alembic.bio ↗
              </a>
            </li>
          </ul>
        </div>
      </div>

      <div className="border-t border-border-subtle">
        <div className="container-content py-4 flex flex-col sm:flex-row items-start sm:items-center justify-between gap-2">
          <p className="text-text-muted text-small">
            in silico exploration · not medical advice · open data
          </p>
          <p className="text-text-subtle text-small select-none">
            {"\u263F"} {new Date().getUTCFullYear()} alembic labs
          </p>
        </div>
      </div>
    </footer>
  );
}
