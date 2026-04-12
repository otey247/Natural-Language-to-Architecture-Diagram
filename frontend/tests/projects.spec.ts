import { expect, test } from "@playwright/test"
import { createUser } from "./utils/privateApi"
import { randomEmail, randomPassword } from "./utils/random"
import { logInUser } from "./utils/user"

test("Projects dashboard is accessible and shows correct title", async ({
  page,
}) => {
  await page.goto("/")
  await expect(
    page.getByRole("heading", { name: "Architecture Projects" }),
  ).toBeVisible()
})

test("New Project button is visible on the dashboard", async ({ page }) => {
  await page.goto("/")
  await expect(page.getByRole("button", { name: "New Project" })).toBeVisible()
})

test.describe("Projects management", () => {
  test.use({ storageState: { cookies: [], origins: [] } })
  let email: string
  const password = randomPassword()

  test.beforeAll(async () => {
    email = randomEmail()
    await createUser({ email, password })
  })

  test("User can log in and see projects dashboard", async ({ page }) => {
    await logInUser(page, email, password)
    await expect(
      page.getByRole("heading", { name: "Architecture Projects" }),
    ).toBeVisible()
  })

  test("User can create a new project", async ({ page }) => {
    await logInUser(page, email, password)

    await page.getByRole("button", { name: "New Project" }).click()

    const dialog = page.getByRole("dialog")
    await expect(dialog).toBeVisible()

    await dialog
      .getByPlaceholder("My Architecture Project")
      .fill("Test Project")
    await dialog.getByRole("button", { name: "Create Project" }).click()

    await expect(page.getByText("Test Project")).toBeVisible()
  })

  test("Empty state is shown when no projects exist for new user", async ({
    page,
  }) => {
    const newEmail = randomEmail()
    await createUser({ email: newEmail, password })
    await logInUser(page, newEmail, password)

    await expect(page.getByText("No projects yet")).toBeVisible()
  })
})
