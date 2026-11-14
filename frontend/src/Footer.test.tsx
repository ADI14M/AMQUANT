import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, describe, expect, it } from 'vitest'
import Footer from './components/Footer'

describe('AMQUANT Official Copyright & Legal Notice Component', () => {
  afterEach(() => {
    cleanup()
  })

  it('renders the compact copyright notice with 2026 Aditya M. on default view', () => {
    render(<Footer />)

    expect(screen.getByText(/© 2026 Aditya M\./i)).toBeInTheDocument()
    expect(screen.getByText(/All Rights Reserved\./i)).toBeInTheDocument()
    expect(
      screen.getByText(/AMQUANT – Quantitative Finance Research & Analytics/i)
    ).toBeInTheDocument()
    expect(
      screen.getByRole('button', { name: /Legal Notice & Disclaimer/i })
    ).toBeInTheDocument()
  })

  it('expands the full legal notice with exact intellectual property text and disclaimer upon clicking toggle', () => {
    render(<Footer />)

    const toggleBtn = screen.getByRole('button', { name: /Legal Notice & Disclaimer/i })
    fireEvent.click(toggleBtn)

    // Verify exact required copyright and intellectual property statement
    expect(
      screen.getByText(
        /AMQUANT is an independently developed quantitative finance research and analytics platform\. Its original software, source code, design, branding, documentation and proprietary materials are the intellectual property of Aditya M, except for third-party components and materials belonging to their respective owners\./i
      )
    ).toBeInTheDocument()

    expect(
      screen.getByText(
        /Unauthorised copying, reproduction, modification, redistribution or commercial use without prior written permission is prohibited\./i
      )
    ).toBeInTheDocument()

    // Verify exact required disclaimer
    expect(
      screen.getByText(
        /AMQUANT is intended for educational, research and analytical purposes only\. Backtesting results and simulations do not guarantee future performance\. Nothing on this platform constitutes financial or investment advice\./i
      )
    ).toBeInTheDocument()

    // Collapse
    const collapseBtn = screen.getByRole('button', { name: /Collapse/i })
    fireEvent.click(collapseBtn)

    expect(
      screen.queryByText(
        /AMQUANT is an independently developed quantitative finance research and analytics platform/i
      )
    ).not.toBeInTheDocument()
  })

  it('opens and closes the dedicated legal notice dialog modal', () => {
    render(<Footer />)

    const modalBtn = screen.getByRole('button', { name: /IP & Disclaimer/i })
    fireEvent.click(modalBtn)

    // Modal dialog is open
    expect(screen.getByRole('dialog')).toBeInTheDocument()
    expect(
      screen.getByRole('heading', { name: /Intellectual Property Notice & Disclaimer/i })
    ).toBeInTheDocument()

    // Contains exact copyright text in modal
    expect(
      screen.getAllByText(/© 2026 Aditya M\. All Rights Reserved\./i).length
    ).toBeGreaterThan(0)

    // Close via Close Notice button
    const closeBtn = screen.getByRole('button', { name: /Close Notice/i })
    fireEvent.click(closeBtn)

    expect(screen.queryByRole('dialog')).not.toBeInTheDocument()
  })
})
